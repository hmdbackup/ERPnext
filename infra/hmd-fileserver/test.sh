#!/usr/bin/env bash
# =============================================================================
# test.sh — Validation de l'installation du serveur de fichiers HMD
# -----------------------------------------------------------------------------
# Vérifie que les groupes, utilisateurs, ACL et services Samba sont
# correctement configurés. Peut être rejoué à tout moment sans effet de bord.
#
# Usage : sudo ./test.sh
# Codes de sortie : 0 = tout OK, 1 = au moins une erreur
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

require_root

# --- Compteurs ----------------------------------------------------------------
PASS=0; FAIL=0

pass() { ok  "$*"; (( PASS++ )); }
fail() { err "$*"; (( FAIL++ )); }

check() {
  local desc="$1" result="$2"
  if [[ "$result" == "ok" ]]; then pass "$desc"
  else                              fail "$desc  ($result)"
  fi
}

# =============================================================================
section() { log ""; log "=== $* ==="; }

# =============================================================================
section "Pré-requis"

for cmd in setfacl getfacl smbpasswd pdbedit testparm; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "Commande disponible : $cmd"
  else
    fail "Commande manquante : $cmd"
  fi
done

# =============================================================================
section "Groupes Linux"

for p in "${PROFILE_GROUPS[@]}"; do
  g="$(resolve_group "$p")"
  if getent group "$g" >/dev/null 2>&1; then
    pass "Groupe existe : $g"
  else
    fail "Groupe manquant : $g"
  fi
done
for g in "$GRP_ALL" "$GRP_STAFF"; do
  if getent group "$g" >/dev/null 2>&1; then
    pass "Groupe existe : $g"
  else
    fail "Groupe manquant : $g"
  fi
done

# =============================================================================
section "Utilisateurs et appartenance aux groupes"

for entry in "${USERS[@]}"; do
  IFS=':' read -r login profile _ _ <<< "$entry"

  # Existence du compte Linux
  if id "$login" >/dev/null 2>&1; then
    pass "Utilisateur existe : $login"
  else
    fail "Utilisateur manquant : $login"
    continue
  fi

  # Appartenance au groupe de profil
  grp_profile="$(resolve_group "$profile")"
  if user_in_group "$login" "$grp_profile"; then
    pass "$login ∈ $grp_profile"
  else
    fail "$login NON MEMBRE de $grp_profile"
  fi

  # Appartenance à hmd_all
  if user_in_group "$login" "$GRP_ALL"; then
    pass "$login ∈ $GRP_ALL"
  else
    fail "$login NON MEMBRE de $GRP_ALL"
  fi

  # hmd_staff : tous sauf guest
  if [[ "$profile" != "guest" ]]; then
    if user_in_group "$login" "$GRP_STAFF"; then
      pass "$login ∈ $GRP_STAFF"
    else
      fail "$login NON MEMBRE de $GRP_STAFF"
    fi
  else
    if ! user_in_group "$login" "$GRP_STAFF"; then
      pass "$login ∉ $GRP_STAFF (correct pour un Guest)"
    else
      fail "$login NE DEVRAIT PAS être dans $GRP_STAFF"
    fi
  fi

  # Compte Samba (sauf guest anonyme)
  if [[ "$login" != "guest" ]]; then
    if pdbedit -u "$login" >/dev/null 2>&1; then
      pass "Compte Samba existe : $login"
    else
      fail "Compte Samba MANQUANT : $login"
    fi
  fi
done

# =============================================================================
section "Répertoires et ACL"

# Vérifie qu'un répertoire existe et que le groupe donné y a les permissions attendues
# check_acl <dir> <groupe> <perms_attendues>   (ex: "rwx" ou "r-x" ou "---")
check_acl() {
  local dir="$1" group="$2" expected="$3"
  if [[ ! -d "$dir" ]]; then
    fail "Répertoire manquant : $dir"
    return
  fi
  local actual
  actual=$(getfacl --omit-header "$dir" 2>/dev/null \
    | grep "^group:${group}:" | head -1 | cut -d: -f3)
  if [[ -z "$actual" ]]; then
    # Essai avec getfacl -n (numérique) puis grep sur le GID
    local gid
    gid=$(getent group "$group" | cut -d: -f3)
    actual=$(getfacl --omit-header --numeric "$dir" 2>/dev/null \
      | grep "^group:${gid}:" | head -1 | cut -d: -f3)
  fi
  if [[ "$actual" == "$expected" ]]; then
    pass "ACL OK  [$expected]  $dir  →  $group"
  else
    fail "ACL KO  [$expected attendu, ${actual:-aucune entrée}]  $dir  →  $group"
  fi
}

admin_g="$(resolve_group admin)"
staff_g="$GRP_STAFF"
all_g="$GRP_ALL"
comptable_g="$(resolve_group comptable)"
gestionnaire_g="$(resolve_group gestionnaire)"
elevage_g="$(resolve_group elevage)"
vegetale_g="$(resolve_group vegetale)"
fromagerie_g="$(resolve_group fromagerie)"

# Racine
check_acl "$HMD_ROOT"                                     "$all_g"          "r-x"
check_acl "$HMD_ROOT"                                     "$admin_g"        "rwx"

# Support
check_acl "$HMD_ROOT/support"                             "$staff_g"        "r-x"
check_acl "$HMD_ROOT/support/administratif"               "$comptable_g"    "rwx"
check_acl "$HMD_ROOT/support/administratif"               "$gestionnaire_g" "r-x"
check_acl "$HMD_ROOT/support/comptabilite"                "$comptable_g"    "rwx"
check_acl "$HMD_ROOT/support/rh"                          "$comptable_g"    "rwx"
check_acl "$HMD_ROOT/support/gestion"                     "$gestionnaire_g" "rwx"
check_acl "$HMD_ROOT/support/gestion"                     "$comptable_g"    "r-x"
check_acl "$HMD_ROOT/support/divers"                      "$comptable_g"    "rwx"
check_acl "$HMD_ROOT/support/divers"                      "$gestionnaire_g" "rwx"
check_acl "$HMD_ROOT/support/dropbox"                     "$all_g"          "rwx"

# Elevage
check_acl "$HMD_ROOT/elevage"                             "$staff_g"        "r-x"
check_acl "$HMD_ROOT/elevage"                             "$elevage_g"      "rwx"
check_acl "$HMD_ROOT/elevage/bovin"                       "$elevage_g"      "rwx"
check_acl "$HMD_ROOT/elevage/ovin"                        "$elevage_g"      "rwx"
check_acl "$HMD_ROOT/elevage/dropbox"                     "$all_g"          "rwx"

# Fromagerie
check_acl "$HMD_ROOT/fromagerie"                          "$staff_g"        "r-x"
check_acl "$HMD_ROOT/fromagerie"                          "$fromagerie_g"   "rwx"
check_acl "$HMD_ROOT/fromagerie/dropbox"                  "$all_g"          "rwx"

# Production végétale
check_acl "$HMD_ROOT/production_vegetale"                 "$staff_g"        "r-x"
check_acl "$HMD_ROOT/production_vegetale"                 "$vegetale_g"     "rwx"
check_acl "$HMD_ROOT/production_vegetale/borj_essebi"     "$vegetale_g"     "rwx"
check_acl "$HMD_ROOT/production_vegetale/tahoura"         "$vegetale_g"     "rwx"
check_acl "$HMD_ROOT/production_vegetale/henchir_gouia"   "$vegetale_g"     "rwx"
check_acl "$HMD_ROOT/production_vegetale/dropbox"         "$all_g"          "rwx"

# IT
check_acl "$HMD_ROOT/it/back-up"                         "$admin_g"        "rwx"
check_acl "$HMD_ROOT/it/software"                        "$all_g"          "rwx"
check_acl "$HMD_ROOT/it/dropbox"                         "$all_g"          "rwx"

# Utilisateurs / Partage
check_acl "$HMD_ROOT/utilisateurs"                       "$all_g"          "r-x"
check_acl "$HMD_ROOT/utilisateurs/partage"               "$all_g"          "rwx"

# Dossiers privés : seul le propriétaire (+ admin) doit avoir accès
check_private() {
  local login="$1"
  local dir="$HMD_ROOT/utilisateurs/$login"
  if [[ ! -d "$dir" ]]; then
    fail "Dossier privé manquant : $dir"
    return
  fi
  local owner
  owner=$(stat -c '%U' "$dir")
  if [[ "$owner" == "$login" ]]; then
    pass "Propriétaire correct : $dir  →  $login"
  else
    fail "Propriétaire incorrect : $dir  →  attendu '$login', actuel '$owner'"
  fi
  # Autres (non propriétaire, non admin) ne doivent pas pouvoir lister
  # On vérifie qu'il n'y a pas d'entrée rwx pour all/staff
  if getfacl --omit-header "$dir" 2>/dev/null | grep -qE "^group:(${all_g}|${staff_g}):"; then
    fail "ALERTE sécurité : $dir exposé au groupe all/staff"
  else
    pass "Dossier privé isolé : $dir"
  fi
}

for entry in "${USERS[@]}"; do
  IFS=':' read -r login _ _ _ <<< "$entry"
  check_private "$login"
done

# =============================================================================
section "Service Samba"

if systemctl is-active smbd >/dev/null 2>&1; then
  pass "smbd est actif"
else
  fail "smbd N'EST PAS actif"
fi

if systemctl is-active nmbd >/dev/null 2>&1; then
  pass "nmbd est actif"
else
  fail "nmbd N'EST PAS actif"
fi

if testparm -s >/dev/null 2>&1; then
  pass "testparm : configuration Samba valide"
else
  fail "testparm : configuration Samba INVALIDE"
fi

# =============================================================================
section "Résumé"

log ""
log "  ✓ Tests réussis : $PASS"
if (( FAIL > 0 )); then
  err "  ✗ Tests échoués : $FAIL"
  log ""
  log "  Relancez setup.sh pour corriger les erreurs."
  exit 1
else
  ok "  Tous les tests sont passés."
fi
