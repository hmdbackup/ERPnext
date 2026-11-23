#!/usr/bin/env bash
# =============================================================================
# check.sh — Bilan de sante du serveur HMD (lecture seule, ne modifie rien)
# Usage :  sudo ./check.sh
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=../hmd-fileserver/lib.sh
source "$HERE/../hmd-fileserver/lib.sh"
require_root

FAIL=0
chk() { # chk "<libelle>" <commande...>
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$label"; else warn "$label : NON"; FAIL=1; fi
}
section() { printf '\n%s== %s ==%s\n' "$C_BLU" "$1" "$C_RST"; }

section "Systeme de fichiers"
chk "fsck.repair=yes au boot"          grep -q 'fsck.repair=yes' /proc/cmdline
chk "/ monte en lecture-ecriture"      findmnt -n -o OPTIONS / -O rw
if [[ -b "$ROOT_LV" ]]; then
  tune2fs -l "$ROOT_LV" 2>/dev/null \
    | grep -E '^(Filesystem state|Mount count|Maximum mount count|Last checked|FS Error count|Last error time)' \
    | sed 's/^/      /'
fi
log "Erreurs noyau (I/O, ext4, USB) :"
dmesg -T 2>/dev/null | grep -iE 'i/o error|ext4-fs (error|warning)|buffer i/o|reset (high|super)-speed usb|blk_update_request' \
  | tail -n 10 | sed 's/^/      /' || true

section "Disques (SMART)"
chk "smartd actif" systemctl is-active --quiet smartmontools
for d in /dev/sd? /dev/nvme?n1; do
  [[ -b "$d" ]] || continue
  h="$(smartctl -H "$d" 2>/dev/null | grep -E 'overall-health|SMART Health Status' | awk -F: '{gsub(/^ +/,"",$2); print $2}')"
  r="$(smartctl -A "$d" 2>/dev/null | awk '$2 ~ /Reallocated_Sector_Ct|Current_Pending_Sector|Offline_Uncorrectable/ {printf "%s=%s ", $2, $10}')"
  [[ -z "$h" ]] && h="(SMART inaccessible : essayer smartctl -d sat -a $d)"
  printf '      %-12s %s %s\n' "$d" "$h" "$r"
done

section "Journaux"
findmnt -n /var/log >/dev/null 2>&1 && findmnt -n -o SOURCE,FSTYPE,SIZE,USED /var/log | sed 's/^/      \/var\/log : /' \
  || log "/var/log sur disque (log2ram inactif)"
journalctl --disk-usage 2>/dev/null | sed 's/^/      /'
df -h /run/log/journal /var/log 2>/dev/null | sed 's/^/      /'

section "ERPNext / Docker"
chk "hmd-erpnext.service active au boot" systemctl is-enabled --quiet hmd-erpnext.service
if command -v docker >/dev/null; then
  log "daemon.json : $( { tr -d "\n " </etc/docker/daemon.json; } 2>/dev/null || echo absent)"
  (cd "$COMPOSE_DIR" 2>/dev/null && docker compose --env-file "$COMPOSE_ENV_FILE" ps --format '{{.Service}}\t{{.State}}\t{{.Status}}' 2>/dev/null | sed 's/^/      /') \
    || warn "docker compose ps impossible dans $COMPOSE_DIR"
fi

section "Onduleur (NUT)"
if command -v upsc >/dev/null; then
  chk "nut-server actif"  systemctl is-active --quiet nut-server
  chk "nut-monitor actif" systemctl is-active --quiet nut-monitor
  st="$(upsc "${UPS_NAME}@localhost" ups.status 2>/dev/null)"
  if [[ -n "$st" ]]; then
    ok "ups.status = $st"
    upsc "${UPS_NAME}@localhost" 2>/dev/null \
      | grep -E '^(battery\.(charge|runtime|charge\.low|runtime\.low|date)|ups\.load|ups\.delay\.(shutdown|start)):' \
      | sed 's/^/      /'
  else
    warn "upsc ne repond pas"; FAIL=1
  fi
  [[ -f "$HMD_ETC/ups-dry-run" ]] && { warn "MODE TEST onduleur actif (aucune extinction reelle)"; FAIL=1; }
  [[ -e /etc/killpower ]] && { warn "/etc/killpower present : le prochain arret coupera l'onduleur"; FAIL=1; }
  log "Derniers evenements onduleur :"
  journalctl -t hmd-ups -n 5 --no-pager -o short-iso 2>/dev/null | sed 's/^/      /'
else
  warn "NUT non installe (./onduleur.sh)"; FAIL=1
fi

echo
(( FAIL )) && { warn "Des points sont a corriger (voir ci-dessus)."; exit 1; }
ok "Tout est en ordre."
