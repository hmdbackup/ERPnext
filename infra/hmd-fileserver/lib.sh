#!/usr/bin/env bash
# =============================================================================
# lib.sh — Fonctions utilitaires partagees
# Sourcé par setup.sh, samba.sh et test.sh. Ne s'execute pas seul.
# =============================================================================

# --- Affichage (couleurs seulement si sortie = terminal) ---------------------
if [[ -t 1 ]]; then
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'; C_BLU=$'\033[34m'; C_RST=$'\033[0m'
else
  C_RED=''; C_GRN=''; C_YEL=''; C_BLU=''; C_RST=''
fi

log()  { printf '%s[i]%s  %s\n'  "$C_BLU" "$C_RST" "$*"; }
ok()   { printf '%s[ok]%s %s\n'  "$C_GRN" "$C_RST" "$*"; }
warn() { printf '%s[!]%s  %s\n'  "$C_YEL" "$C_RST" "$*" >&2; }
err()  { printf '%s[x]%s  %s\n'  "$C_RED" "$C_RST" "$*" >&2; }

require_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    err "Ce script doit etre execute en root (utilisez sudo)."
    exit 1
  fi
}

# resolve_group <token> -> nom de groupe Linux reel
#   ALL   -> $GRP_ALL          STAFF -> $GRP_STAFF
#   <p>   -> ${GP}_<p>         (admin -> hmd_admin, comptable -> hmd_comptable...)
resolve_group() {
  case "$1" in
    ALL)   printf '%s' "$GRP_ALL" ;;
    STAFF) printf '%s' "$GRP_STAFF" ;;
    *)     printf '%s_%s' "$GP" "$1" ;;
  esac
}

# user_groups <profil> -> liste (separee par des espaces) des groupes
# SUPPLEMENTAIRES auxquels appartient un utilisateur de ce profil.
user_groups() {
  local profile="$1"
  local groups=()
  groups+=( "$(resolve_group "$profile")" )   # groupe du profil
  groups+=( "$GRP_ALL" )                        # « All »
  if [[ "$profile" != "guest" ]]; then
    groups+=( "$GRP_STAFF" )                     # « All - Guest »
  fi
  printf '%s' "${groups[*]}"
}

# user_in_group <login> <groupe> -> code retour 0 si <login> appartient au
# groupe (interroge le systeme reel, pas la config -> verifie l'etat applique).
user_in_group() {
  id -nG "$1" 2>/dev/null | tr ' ' '\n' | grep -qx "$2"
}

# resolve_valid_users <csv_tokens> -> "@grp1 @grp2 ..." pour smb.conf
resolve_valid_users() {
  local csv="$1" out='' tok g
  local toks=()
  IFS=',' read -ra toks <<<"$csv"
  for tok in "${toks[@]}"; do
    g="$(resolve_group "$tok")"
    out+=" @${g}"
  done
  printf '%s' "${out# }"
}
