#!/usr/bin/env bash
# =============================================================================
# config.sh — Parametres du serveur HMD (stabilisation + onduleur)
# Sourcé par stabilite.sh, onduleur.sh et check.sh. A adapter avant execution.
# =============================================================================

# --- Pile ERPNext (Docker) ----------------------------------------------------
# Dossier frappe_docker contenant .env (COMPOSE_FILE y est defini).
COMPOSE_DIR="/home/hmd/hmd-deploy/frappe_docker"
COMPOSE_ENV_FILE=".env"
# Delai (s) laisse aux conteneurs (MariaDB surtout) pour s'arreter proprement.
COMPOSE_STOP_TIMEOUT=60

# --- Volumes -----------------------------------------------------------------
ROOT_LV="/dev/mapper/ubuntu--vg-ubuntu--lv"

# --- Journaux ----------------------------------------------------------------
# log2ram  : /var/log en RAM + synchro disque horaire et a l'arret (recommande)
# volatile : journald en RAM uniquement (perdu a chaque reboot / coupure)
# none     : ne touche pas aux journaux
LOG_MODE="log2ram"
LOG2RAM_SIZE="128M"        # taille du tmpfs /var/log
JOURNAL_MAX_USE="40M"      # plafond journald (doit tenir dans LOG2RAM_SIZE)

# --- Docker ------------------------------------------------------------------
DOCKER_SHUTDOWN_TIMEOUT=60 # s, arret des conteneurs a l'arret du daemon
DOCKER_LOG_MAX_SIZE="10m"
DOCKER_LOG_MAX_FILE="3"

# --- Onduleur (NUT) ----------------------------------------------------------
UPS_NAME="hmdups"
UPS_DRIVER="usbhid-ups"    # APC/Eaton/CyberPower USB. Chinois/generique : nutdrv_qx
UPS_PORT="auto"
UPS_DESC="Onduleur serveur HMD"

# Declenchement de l'extinction : le PREMIER des criteres atteint.
UPS_LOW_CHARGE=50          # % batterie restant
UPS_LOW_RUNTIME=300        # s d'autonomie restante estimee par l'onduleur
ONBATT_MAX_SEC="${ONBATT_MAX_SEC:-300}"  # s sur batterie avant extinction (coupure longue)

# Apres l'arret, NUT ordonne a l'onduleur de couper puis de retablir sa sortie
# au retour du secteur -> le serveur redemarre seul (BIOS : "Power On" apres
# perte AC). Si le secteur revient pendant l'arret, le serveur reboote apres :
POWEROFF_WAIT="180s"

# Fichiers installes
HMD_ETC="/etc/hmd-server"
