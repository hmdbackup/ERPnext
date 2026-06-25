#!/usr/bin/env bash
# =============================================================================
# setup.sh — Installation du serveur de fichiers HMD
# -----------------------------------------------------------------------------
#  - cree les groupes (profils + agreges)
#  - cree les utilisateurs et leur affectation aux groupes
#  - cree l'arborescence et applique les ACL POSIX (lecture/ecriture fines)
#  - cree les dossiers personnels « Private »
#  - configure Samba (sauf si --no-samba)
#
# Idempotent : peut etre relance sans danger. Les ACL sont reinitialisees a
# chaque passage pour rester deterministes.
#
# Usage :  sudo ./setup.sh [--no-samba]
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

DO_SAMBA=1
for arg in "$@"; do
  case "$arg" in
    --no-samba) DO_SAMBA=0 ;;
    -h|--help)
      echo "Usage: sudo $0 [--no-samba]"
      echo "  --no-samba   N'installe/configure pas Samba (couche fichiers/ACL seule)."
      exit 0 ;;
    *) err "Argument inconnu : $arg"; exit 1 ;;
  esac
done

require_root

# -----------------------------------------------------------------------------
ensure_packages() {
  local pkgs=(acl attr)
  (( DO_SAMBA )) && pkgs+=(samba)
  local missing=()
  local p
  for p in "${pkgs[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
  done
  if (( ${#missing[@]} )); then
    log "Installation des paquets : ${missing[*]}"
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
  fi
  ok "Paquets requis presents : ${pkgs[*]}"
}

# -----------------------------------------------------------------------------
create_groups() {
  log "Creation des groupes..."
  local p g
  for p in "${PROFILE_GROUPS[@]}"; do
    g="$(resolve_group "$p")"
    if getent group "$g" >/dev/null; then
      :
    else
      groupadd "$g"; ok "groupe cree : $g"
    fi
  done
  for g in "$GRP_ALL" "$GRP_STAFF"; do
    getent group "$g" >/dev/null || { groupadd "$g"; ok "groupe cree : $g"; }
  done
}

# -----------------------------------------------------------------------------
create_users() {
  log "Creation des utilisateurs et affectation aux groupes..."
  local entry login profile fullname shell sh supp
  for entry in "${USERS[@]}"; do
    IFS=':' read -r login profile fullname shell <<<"$entry"
    case "$shell" in
      bash) sh="/bin/bash" ;;
      *)    sh="/usr/sbin/nologin" ;;
    esac

    if id "$login" >/dev/null 2>&1; then
      usermod --shell "$sh" --comment "$fullname" "$login"
    else
      useradd --create-home --user-group --shell "$sh" --comment "$fullname" "$login"
      ok "utilisateur cree : $login ($fullname)"
    fi

    # Groupes supplementaires (profil + hmd_all + hmd_staff)
    supp="$(user_groups "$profile")"
    usermod -aG "${supp// /,}" "$login"

    # Les admins recoivent sudo (administration en SSH)
    if [[ "$profile" == "admin" ]]; then
      getent group sudo >/dev/null && usermod -aG sudo "$login"
    fi
  done
}

# -----------------------------------------------------------------------------
# Mots de passe Linux (SSH / console) pour les comptes interactifs (shell=bash).
# Le mot de passe Linux est DISTINCT du mot de passe Samba : il est requis pour
# l'acces SSH des administrateurs. Idempotent : un mot de passe deja defini
# (status « P ») n'est jamais ecrase.
set_linux_passwords() {
  log "Definition des mots de passe Linux (comptes interactifs)..."
  local first=1 entry login profile fullname shell status pwd

  for entry in "${USERS[@]}"; do
    IFS=':' read -r login profile fullname shell <<<"$entry"
    [[ "$shell" == "bash" ]] || continue        # seulement les comptes interactifs

    status="$(passwd -S "$login" 2>/dev/null | awk '{print $2}')"
    if [[ "$status" == "P" ]]; then
      ok "Mot de passe Linux deja defini, conserve : $login"
      continue
    fi

    if (( first )); then
      : > "$LINUX_CRED_FILE"
      chmod 600 "$LINUX_CRED_FILE"
      printf '# Mots de passe Linux (SSH) initiaux HMD — %s\n' "$(date)" >> "$LINUX_CRED_FILE"
      printf '# Changez-les : passwd <login>\n\n' >> "$LINUX_CRED_FILE"
      first=0
    fi

    # dd lit un bloc fixe -> evite SIGPIPE avec set -o pipefail
    pwd=$(dd if=/dev/urandom bs=128 count=1 2>/dev/null | tr -dc 'A-Za-z0-9@#%!' | cut -c1-16)
    printf '%s:%s\n' "$login" "$pwd" | chpasswd
    printf '%-15s : %s\n' "$login" "$pwd" >> "$LINUX_CRED_FILE"
    ok "Mot de passe Linux defini : $login"
  done

  if (( ! first )); then
    warn "Mots de passe Linux initiaux dans : $LINUX_CRED_FILE (root seulement)"
    warn "→ Changer un mot de passe :  passwd <login>"
  fi
}

# -----------------------------------------------------------------------------
# apply_acl <dossier_absolu> <lecture_csv> <ecriture_csv>
#   Base : proprietaire root, groupe hmd_admin, setgid, aucun acces « autres ».
#   Puis ACL nommees (acces + heritage) pour les groupes lecture/ecriture.
apply_acl() {
  local dir="$1" read_csv="$2" write_csv="$3"
  local admin tok g
  local toks=()
  admin="$(resolve_group admin)"

  # ACL de base : owner rwx, mask rwx, autres rien, admin rwx
  local acl="u::rwx,g::rwx,o::---,m::rwx,g:${admin}:rwx"

  if [[ -n "$read_csv" ]]; then
    IFS=',' read -ra toks <<<"$read_csv"
    for tok in "${toks[@]}"; do
      g="$(resolve_group "$tok")"
      acl+=",g:${g}:rx"
    done
  fi
  if [[ -n "$write_csv" ]]; then
    IFS=',' read -ra toks <<<"$write_csv"
    for tok in "${toks[@]}"; do
      g="$(resolve_group "$tok")"
      acl+=",g:${g}:rwx"
    done
  fi

  chown root:"$admin" "$dir"
  chmod 2770 "$dir"            # setgid + rwx owner/group, rien pour « autres »
  setfacl -b "$dir"           # remise a zero -> resultat deterministe en re-run
  setfacl -m "$acl" "$dir"    # ACL d'acces
  setfacl -d -m "$acl" "$dir" # ACL par defaut -> heritee par tout nouveau contenu
}

# -----------------------------------------------------------------------------
# Garantit que tous les dossiers PARENTS de HMD_ROOT sont traversables (--x)
# par tous. Indispensable quand HMD_ROOT est placé sous un dossier personnel
# (ex: /home/hmd/partage_windows) : /home/hmd est en 750 par defaut et bloque
# l'acces des autres utilisateurs. On ajoute seulement o+x (traversee), jamais
# o+r : le contenu des dossiers parents reste non listable.
ensure_parents_traversable() {
  local p
  p="$(dirname "$HMD_ROOT")"
  while [[ "$p" != "/" && -n "$p" ]]; do
    chmod o+x "$p" 2>/dev/null || warn "Impossible d'ajouter o+x sur $p"
    p="$(dirname "$p")"
  done
}

# -----------------------------------------------------------------------------
setup_dirs() {
  log "Creation de l'arborescence et application des ACL..."
  mkdir -p "$HMD_ROOT"
  ensure_parents_traversable

  local entry rel read_csv write_csv abspath
  for entry in "${DIRS[@]}"; do
    IFS='|' read -r rel read_csv write_csv <<<"$entry"
    if [[ "$rel" == "." ]]; then
      abspath="$HMD_ROOT"
    else
      abspath="$HMD_ROOT/$rel"
    fi
    mkdir -p "$abspath"
    apply_acl "$abspath" "$read_csv" "$write_csv"
  done

  # Droit de TRAVERSEE (--x) pour atteindre les DropBox/Software « All »
  local g_all
  g_all="$GRP_ALL"
  for rel in "${TRAVERSE_ALL_DIRS[@]}"; do
    setfacl -m "g:${g_all}:x" "$HMD_ROOT/$rel"
  done
  ok "Arborescence + ACL appliquees."
}

# -----------------------------------------------------------------------------
# Dossiers personnels « Private » : proprietaire = l'utilisateur, + admin.
setup_private_dirs() {
  log "Creation des dossiers personnels (Private)..."
  local base="$HMD_ROOT/utilisateurs"
  local admin entry login profile fullname shell dir
  admin="$(resolve_group admin)"

  for entry in "${USERS[@]}"; do
    IFS=':' read -r login profile fullname shell <<<"$entry"
    dir="$base/$login"
    mkdir -p "$dir"
    # Propriétaire = l'utilisateur (rwx via u::rwx), groupe = hmd_admin (rwx), autres = rien
    chown "$login":"$admin" "$dir"
    chmod 2770 "$dir"
    setfacl -b "$dir"
    setfacl -m  "u::rwx,g::rwx,o::---,m::rwx,g:${admin}:rwx" "$dir"
    setfacl -d -m "u::rwx,g::rwx,o::---,m::rwx,g:${admin}:rwx" "$dir"
  done
  ok "Dossiers personnels crees (acces : proprietaire + admin)."
}

# -----------------------------------------------------------------------------
main() {
  log "=== Installation serveur de fichiers HMD (racine : $HMD_ROOT) ==="
  ensure_packages
  create_groups
  create_users
  set_linux_passwords
  setup_dirs
  setup_private_dirs

  if (( DO_SAMBA )); then
    # shellcheck source=samba.sh
    source "$HERE/samba.sh"
    configure_samba
  else
    warn "Samba ignore (--no-samba). Couche fichiers/ACL seule."
  fi

  ok "=== Installation terminee ==="
  log "Validez avec :  sudo $HERE/test.sh"
}

main
