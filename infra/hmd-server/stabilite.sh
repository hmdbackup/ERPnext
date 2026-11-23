#!/usr/bin/env bash
# =============================================================================
# stabilite.sh — Stabilisation du serveur HMD apres l'incident fsck/initramfs
# -----------------------------------------------------------------------------
#  1. fsck automatique au boot (fsck.repair=yes) : plus de blocage BusyBox
#  2. Journaux en RAM (log2ram ou journald volatile) + plafond journald
#  3. Docker : rotation des logs conteneurs + delai d'arret pour MariaDB
#  4. Service hmd-erpnext : demarrage au boot + arret propre avant Docker
#  5. Surveillance SMART (smartd) des disques
#  6. Controle /etc/fstab du disque USB (nofail) — avertissement seulement
#
# Idempotent. Les fichiers modifies sont sauvegardes une fois en *.orig-hmd.
# Usage :  sudo ./stabilite.sh [--skip-logs] [--skip-docker] [--skip-grub]
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=../hmd-fileserver/lib.sh
source "$HERE/../hmd-fileserver/lib.sh"

DO_LOGS=1; DO_DOCKER=1; DO_GRUB=1
for arg in "$@"; do
  case "$arg" in
    --skip-logs)   DO_LOGS=0 ;;
    --skip-docker) DO_DOCKER=0 ;;
    --skip-grub)   DO_GRUB=0 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) err "Argument inconnu : $arg"; exit 1 ;;
  esac
done

require_root
REBOOT_NEEDED=0

backup_once() { [[ -f "$1" && ! -f "$1.orig-hmd" ]] && cp -a "$1" "$1.orig-hmd" || true; }

apt_install() {
  local missing=() p
  for p in "$@"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
  if (( ${#missing[@]} )); then
    log "Installation : ${missing[*]}"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
  fi
}

# -----------------------------------------------------------------------------
setup_fsck() {
  (( DO_GRUB )) || { warn "GRUB ignore (--skip-grub)"; return; }
  local f=/etc/default/grub
  if grep -qE '^GRUB_CMDLINE_LINUX_DEFAULT=.*fsck\.repair=yes' "$f"; then
    ok "fsck.repair=yes deja present"
  else
    backup_once "$f"
    sed -i -E 's/^(GRUB_CMDLINE_LINUX_DEFAULT=")([^"]*)"/\1\2 fsck.repair=yes"/; s/=" /="/' "$f"
    update-grub >/dev/null 2>&1
    REBOOT_NEEDED=1
    ok "fsck.repair=yes ajoute (initramfs repare seul au lieu de basculer sur BusyBox)"
  fi
  # Option errors=remount-ro sur / : le noyau protege le FS au lieu de continuer a ecrire
  if awk '$2=="/" && $4 !~ /errors=remount-ro/ {f=1} END{exit !f}' /etc/fstab; then
    warn "/ n'a pas errors=remount-ro dans /etc/fstab (recommande)"
  fi
  # Verification periodique ext4 (tous les 30 montages ou 3 mois)
  if [[ -b "$ROOT_LV" ]]; then
    tune2fs -c 30 -i 3m "$ROOT_LV" >/dev/null && ok "tune2fs : fsck tous les 30 montages / 3 mois"
  fi
}

# -----------------------------------------------------------------------------
setup_journald() {
  local storage="$1" key="$2"
  mkdir -p /etc/systemd/journald.conf.d
  cat >/etc/systemd/journald.conf.d/90-hmd.conf <<EOF
# Gere par infra/hmd-server/stabilite.sh
[Journal]
Storage=${storage}
${key}=${JOURNAL_MAX_USE}
Compress=yes
MaxRetentionSec=1month
EOF
  systemctl restart systemd-journald
  ok "journald : Storage=${storage}, ${key}=${JOURNAL_MAX_USE}"
}

setup_logs() {
  (( DO_LOGS )) || { warn "Journaux ignores (--skip-logs)"; return; }
  case "$LOG_MODE" in
    none) warn "LOG_MODE=none : journaux inchanges"; return ;;
    volatile)
      setup_journald volatile RuntimeMaxUse
      rm -rf /var/log/journal/*
      warn "journald volatile : AUCUN journal ne survivra a un reboot / une coupure"
      return ;;
    log2ram) ;;
    *) err "LOG_MODE invalide : $LOG_MODE"; exit 1 ;;
  esac

  # Le journal persistant vit dans /var/log/journal -> en RAM via log2ram,
  # synchronise sur disque. Plafond strict pour tenir dans le tmpfs.
  setup_journald persistent SystemMaxUse
  journalctl --vacuum-size="$JOURNAL_MAX_USE" >/dev/null 2>&1 || true

  if ! dpkg -s log2ram >/dev/null 2>&1; then
    apt_install curl gnupg rsync
    log "Ajout du depot log2ram (packages.azlux.fr)"
    curl -fsSL https://azlux.fr/repo.gpg -o /usr/share/keyrings/azlux-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/azlux-archive-keyring.gpg] http://packages.azlux.fr/debian/ bookworm main" \
      >/etc/apt/sources.list.d/azlux.list
    apt_install log2ram
    REBOOT_NEEDED=1
  fi
  backup_once /etc/log2ram.conf
  sed -i -E "s/^SIZE=.*/SIZE=${LOG2RAM_SIZE}/; s/^USE_RSYNC=.*/USE_RSYNC=true/; s/^MAIL=.*/MAIL=false/" /etc/log2ram.conf
  systemctl enable log2ram >/dev/null 2>&1 || true

  local used_mb limit_mb
  used_mb=$(du -sm /var/log 2>/dev/null | awk '{print $1}')
  limit_mb=$(numfmt --from=iec "${LOG2RAM_SIZE}" | awk '{print int($1/1048576)}')
  if (( used_mb * 100 > limit_mb * 70 )); then
    warn "/var/log = ${used_mb} Mo (> 70% de ${LOG2RAM_SIZE}) : log2ram refusera de monter."
    warn "Nettoyer (ex: anciens *.gz, /var/log/journal) ou augmenter LOG2RAM_SIZE."
  fi
  ok "log2ram : SIZE=${LOG2RAM_SIZE} (actif apres reboot)"
}

# -----------------------------------------------------------------------------
setup_docker() {
  (( DO_DOCKER )) || { warn "Docker ignore (--skip-docker)"; return; }
  command -v docker >/dev/null || { warn "Docker absent : etape ignoree"; return; }

  local f=/etc/docker/daemon.json
  mkdir -p /etc/docker
  backup_once "$f"
  python3 - "$f" "$DOCKER_SHUTDOWN_TIMEOUT" "$DOCKER_LOG_MAX_SIZE" "$DOCKER_LOG_MAX_FILE" <<'PY'
import json, os, sys
path, timeout, size, nfile = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
cfg = {}
if os.path.exists(path) and os.path.getsize(path):
    with open(path) as fh:
        cfg = json.load(fh)
cfg["shutdown-timeout"] = timeout
cfg.setdefault("log-driver", "local")
cfg.setdefault("log-opts", {}).update({"max-size": size, "max-file": nfile})
with open(path, "w") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")
PY
  ok "daemon.json : shutdown-timeout=${DOCKER_SHUTDOWN_TIMEOUT}s, logs ${DOCKER_LOG_MAX_SIZE} x ${DOCKER_LOG_MAX_FILE}"
  warn "daemon.json pris en compte au prochain reboot (ou : systemctl restart docker)."
  warn "Rotation des logs : seulement pour les conteneurs recrees (docker compose up -d --force-recreate)."

  # Service systemd ERPNext
  if [[ ! -f "$COMPOSE_DIR/$COMPOSE_ENV_FILE" ]]; then
    warn "$COMPOSE_DIR/$COMPOSE_ENV_FILE introuvable : hmd-erpnext.service non installe (verifier COMPOSE_DIR)"
    return
  fi
  mkdir -p "$HMD_ETC"
  cat >"$HMD_ETC/erpnext.env" <<EOF
COMPOSE_ENV_FILE=${COMPOSE_ENV_FILE}
COMPOSE_STOP_TIMEOUT=${COMPOSE_STOP_TIMEOUT}
EOF
  sed -e "s|@HMD_ETC@|$HMD_ETC|g" -e "s|@COMPOSE_DIR@|$COMPOSE_DIR|g" \
      -e "s|@STOP_TIMEOUT_SEC@|$((COMPOSE_STOP_TIMEOUT + 60))|g" \
      "$HERE/files/hmd-erpnext.service" >/etc/systemd/system/hmd-erpnext.service
  systemctl daemon-reload
  # enable sans --now : la pile tourne deja ; le service prendra la main au reboot
  systemctl enable hmd-erpnext.service >/dev/null 2>&1
  ok "hmd-erpnext.service actif au boot (arret propre ${COMPOSE_STOP_TIMEOUT}s avant Docker)"
}

# -----------------------------------------------------------------------------
setup_smart() {
  apt_install smartmontools
  local f=/etc/smartd.conf
  backup_once "$f"
  # Tous les disques (USB inclus si le pont le permet) ; alertes dans syslog.
  # Test court quotidien 02h, long le samedi 03h ; ne reveille pas un disque en veille.
  cat >"$f" <<'EOF'
# Gere par infra/hmd-server/stabilite.sh
DEVICESCAN -d removable -a -o on -S on -n standby,q -s (S/../.././02|L/../../6/03) -W 4,45,55
EOF
  systemctl enable --now smartmontools >/dev/null 2>&1 || systemctl enable --now smartd >/dev/null 2>&1 || true
  systemctl restart smartmontools >/dev/null 2>&1 || systemctl restart smartd >/dev/null 2>&1 || true
  ok "smartd : surveillance SMART active (journalctl -u smartmontools)"
}

# -----------------------------------------------------------------------------
check_fstab_usb() {
  # Une entree fstab sans nofail vers un disque USB absent bloque le boot (emergency mode)
  local line bad=0
  while read -r line; do
    [[ -z "$line" || "$line" == \#* ]] && continue
    # shellcheck disable=SC2086
    set -- $line
    [[ "$2" == "/" || "$2" == "/boot"* || "$2" == "none" || "$3" == "swap" ]] && continue
    case "$3" in tmpfs|proc|sysfs|devpts) continue ;; esac
    if [[ "$4" != *nofail* ]]; then
      warn "fstab : '$2' ($1) sans 'nofail' — si c'est le disque USB, ajouter : nofail,x-systemd.device-timeout=10s"
      bad=1
    fi
  done </etc/fstab
  (( bad )) || ok "fstab : montages secondaires en nofail"
}

# -----------------------------------------------------------------------------
setup_fsck
setup_logs
setup_docker
setup_smart
check_fstab_usb

echo
if (( REBOOT_NEEDED )); then
  warn "Redemarrage necessaire pour activer fsck.repair / log2ram : sudo reboot"
fi
ok "Stabilisation terminee. Verification : sudo $HERE/check.sh"
