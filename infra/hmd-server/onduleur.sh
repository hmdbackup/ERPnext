#!/usr/bin/env bash
# =============================================================================
# onduleur.sh — Extinction automatique du serveur HMD sur coupure de courant
# -----------------------------------------------------------------------------
# NUT (Network UPS Tools), mode standalone, onduleur en USB sur ce serveur.
# Extinction propre declenchee par le PREMIER de ces evenements :
#   - batterie < UPS_LOW_CHARGE %  ou  autonomie < UPS_LOW_RUNTIME s
#   - secteur absent depuis ONBATT_MAX_SEC s
# Sequence : upsmon -> hmd-ups-shutdown -> systemd arrete hmd-erpnext (MariaDB
# propre) -> Docker -> FS demontes -> NUT coupe l'onduleur -> au retour du
# secteur l'onduleur se rallume et le serveur redemarre (BIOS "Power On").
#
# Usage :  sudo ./onduleur.sh              installe / reconfigure (mode reel)
#          sudo ./onduleur.sh --dry-run    mode test : journalise, n'eteint pas
#          sudo ./onduleur.sh --activer    quitte le mode test
#          sudo ./onduleur.sh --force      installe meme sans onduleur detecte
# Test rapide : sudo ONBATT_MAX_SEC=30 ./onduleur.sh --dry-run
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=../hmd-fileserver/lib.sh
source "$HERE/../hmd-fileserver/lib.sh"

DRY=""; FORCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=on ;;
    --activer) DRY=off ;;
    --force)   FORCE=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) err "Argument inconnu : $arg"; exit 1 ;;
  esac
done

require_root
NUT=/etc/nut

backup_once() { [[ -f "$1" && ! -f "$1.orig-hmd" ]] && cp -a "$1" "$1.orig-hmd" || true; }

# -----------------------------------------------------------------------------
install_packages() {
  if ! dpkg -s nut-server nut-client >/dev/null 2>&1; then
    log "Installation de NUT"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y nut nut-server nut-client
  fi
  ok "NUT installe ($(dpkg-query -W -f='${Version}' nut-client))"
  udevadm control --reload-rules 2>/dev/null || true
  udevadm trigger --subsystem-match=usb 2>/dev/null || true
}

detect_ups() {
  local scan
  scan="$(nut-scanner -U -q 2>/dev/null || true)"
  if [[ -z "$scan" ]]; then
    if (( FORCE )); then
      warn "Aucun onduleur USB detecte (--force : on continue)"
      return
    fi
    err "Aucun onduleur USB detecte (nut-scanner -U). Verifier le cable USB / lsusb."
    err "Onduleur serie ou modele exotique : adapter UPS_DRIVER/UPS_PORT puis --force."
    exit 1
  fi
  local found
  found="$(awk -F'"' '/driver *=/ {print $2; exit}' <<<"$scan")"
  ok "Onduleur detecte : driver ${found:-?} — $(awk -F'"' '/product *=/ {print $2; exit}' <<<"$scan")"
  if [[ -n "$found" && "$found" != "$UPS_DRIVER" ]]; then
    warn "nut-scanner propose '$found' (config : '$UPS_DRIVER') -> utilisation de '$found'"
    UPS_DRIVER="$found"
  fi
}

# Mot de passe upsmon : conserve s'il existe deja (idempotence)
upsmon_password() {
  local p=""
  [[ -f $NUT/upsd.users ]] && p="$(awk '/^\[upsmon_hmd\]/{f=1;next} /^\[/{f=0} f && $1=="password" {print $3; exit}' $NUT/upsd.users)"
  [[ -n "$p" ]] || p="$(head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 24)"
  printf '%s' "$p"
}

# NUT >= 2.8 : "primary" ; 2.7 (Ubuntu 22.04) : "master"
upsmon_role() {
  if dpkg --compare-versions "$(dpkg-query -W -f='${Version}' nut-client)" ge 2.8; then
    echo primary
  else
    echo master
  fi
}

# -----------------------------------------------------------------------------
write_config() {
  local pass role f
  pass="$(upsmon_password)"; role="$(upsmon_role)"
  for f in nut.conf ups.conf upsd.conf upsd.users upsmon.conf upssched.conf; do
    backup_once "$NUT/$f"
  done

  cat >$NUT/nut.conf <<EOF
# Gere par infra/hmd-server/onduleur.sh
MODE=standalone
# Si le secteur revient pendant l'extinction, reboot apres ce delai
POWEROFF_WAIT=${POWEROFF_WAIT}
EOF

  cat >$NUT/ups.conf <<EOF
# Gere par infra/hmd-server/onduleur.sh
maxretry = 3

[${UPS_NAME}]
  driver = ${UPS_DRIVER}
  port = ${UPS_PORT}
  desc = "${UPS_DESC}"
  pollinterval = 15
  # Le driver signale "batterie faible" (LB) selon nos seuils, pas ceux de l'onduleur
  ignorelb
  override.battery.charge.low = ${UPS_LOW_CHARGE}
  override.battery.runtime.low = ${UPS_LOW_RUNTIME}
EOF

  cat >$NUT/upsd.conf <<'EOF'
# Gere par infra/hmd-server/onduleur.sh
LISTEN 127.0.0.1 3493
LISTEN ::1 3493
EOF

  cat >$NUT/upsd.users <<EOF
# Gere par infra/hmd-server/onduleur.sh
[upsmon_hmd]
  password = ${pass}
  upsmon ${role}
EOF

  cat >$NUT/upsmon.conf <<EOF
# Gere par infra/hmd-server/onduleur.sh
MONITOR ${UPS_NAME}@localhost 1 upsmon_hmd ${pass} ${role}
MINSUPPLIES 1
SHUTDOWNCMD "/usr/local/sbin/hmd-ups-shutdown"
NOTIFYCMD /sbin/upssched
POWERDOWNFLAG "/etc/killpower"
POLLFREQ 5
POLLFREQALERT 5
HOSTSYNC 15
DEADTIME 15
FINALDELAY 5
RBWARNTIME 43200
NOCOMMWARNTIME 300

NOTIFYFLAG ONLINE   SYSLOG+WALL+EXEC
NOTIFYFLAG ONBATT   SYSLOG+WALL+EXEC
NOTIFYFLAG LOWBATT  SYSLOG+WALL+EXEC
NOTIFYFLAG FSD      SYSLOG+WALL
NOTIFYFLAG COMMOK   SYSLOG+EXEC
NOTIFYFLAG COMMBAD  SYSLOG+WALL+EXEC
NOTIFYFLAG NOCOMM   SYSLOG+WALL+EXEC
NOTIFYFLAG REPLBATT SYSLOG+WALL+EXEC
NOTIFYFLAG SHUTDOWN SYSLOG+WALL
EOF

  cat >$NUT/upssched.conf <<EOF
# Gere par infra/hmd-server/onduleur.sh
CMDSCRIPT /usr/local/sbin/hmd-upssched-cmd
PIPEFN /run/nut/upssched.pipe
LOCKFN /run/nut/upssched.lock

AT ONBATT   * START-TIMER onbatt_timeout ${ONBATT_MAX_SEC}
AT ONBATT   * EXECUTE onbatt
AT ONLINE   * CANCEL-TIMER onbatt_timeout
AT ONLINE   * EXECUTE online
AT LOWBATT  * EXECUTE lowbatt
AT COMMBAD  * EXECUTE commbad
AT NOCOMM   * EXECUTE commbad
AT COMMOK   * EXECUTE commok
AT REPLBATT * EXECUTE replbatt
EOF

  chown root:nut $NUT/*.conf $NUT/upsd.users
  chmod 640 $NUT/*.conf $NUT/upsd.users
  ok "Configuration NUT ecrite (${UPS_NAME}, ${UPS_DRIVER}, upsmon ${role})"

  install -m 0755 "$HERE/files/hmd-ups-shutdown"  /usr/local/sbin/hmd-ups-shutdown
  install -m 0755 "$HERE/files/hmd-upssched-cmd"  /usr/local/sbin/hmd-upssched-cmd

  # upssched tourne en 'nut' ; upsmon -c fsd doit signaler le processus root
  local s=/etc/sudoers.d/hmd-nut
  echo 'nut ALL=(root) NOPASSWD: /sbin/upsmon -c fsd' >"$s.tmp"
  chmod 440 "$s.tmp"
  visudo -cf "$s.tmp" >/dev/null && mv "$s.tmp" "$s"
  ok "Scripts installes : /usr/local/sbin/hmd-ups-shutdown, hmd-upssched-cmd"
}

set_dry_run() {
  mkdir -p "$HMD_ETC"
  case "$DRY" in
    on)  touch "$HMD_ETC/ups-dry-run"; warn "MODE TEST actif : aucune extinction reelle (retirer : --activer)" ;;
    off) rm -f "$HMD_ETC/ups-dry-run"; ok "Mode reel actif" ;;
    *)   [[ -f "$HMD_ETC/ups-dry-run" ]] && warn "MODE TEST toujours actif (--activer pour le retirer)" || true ;;
  esac
}

# -----------------------------------------------------------------------------
start_services() {
  systemctl daemon-reload
  if systemctl cat nut-driver-enumerator.service >/dev/null 2>&1; then
    systemctl restart nut-driver-enumerator.service
    systemctl enable nut-driver.target >/dev/null 2>&1 || true
    systemctl restart nut-driver.target
  else
    systemctl enable --now nut-driver.service >/dev/null 2>&1 || true
    systemctl restart nut-driver.service
  fi
  systemctl enable nut-server.service nut-monitor.service >/dev/null 2>&1
  systemctl restart nut-server.service
  sleep 2
  systemctl restart nut-monitor.service
  ok "Services NUT demarres"
}

verify() {
  local st
  for _ in 1 2 3 4 5; do
    st="$(upsc "${UPS_NAME}@localhost" ups.status 2>/dev/null || true)"
    [[ -n "$st" ]] && break
    sleep 2
  done
  if [[ -z "$st" ]]; then
    err "upsc ne repond pas : journalctl -u 'nut-*' -n 50"
    exit 1
  fi
  ok "ups.status = $st   (OL = secteur, OB = batterie, LB = batterie faible)"
  upsc "${UPS_NAME}@localhost" 2>/dev/null \
    | grep -E '^(device\.(mfr|model)|battery\.(charge|runtime|charge\.low|runtime\.low)|ups\.load|ups\.delay\.(shutdown|start)):' \
    | sed 's/^/      /' || true
  if ! upsc "${UPS_NAME}@localhost" battery.charge >/dev/null 2>&1; then
    warn "L'onduleur ne remonte pas battery.charge : seul le delai ONBATT_MAX_SEC protege le serveur"
  fi
  systemctl is-enabled hmd-erpnext.service >/dev/null 2>&1 \
    || warn "hmd-erpnext.service absent : lancer d'abord ./stabilite.sh (arret propre de MariaDB)"
}

# -----------------------------------------------------------------------------
install_packages
detect_ups
write_config
set_dry_run
start_services
verify
echo
ok "Onduleur configure. Extinction : charge<${UPS_LOW_CHARGE}% | autonomie<${UPS_LOW_RUNTIME}s | ${ONBATT_MAX_SEC}s sur batterie"
log "BIOS : regler 'Restore on AC Power Loss' = 'Power On' pour le redemarrage automatique."
