#!/usr/bin/env bash
# =============================================================================
# samba.sh — Configuration Samba du serveur de fichiers HMD
# -----------------------------------------------------------------------------
# Sourcé par setup.sh (ne s'exécute pas seul).
# Génère /etc/samba/smb.conf à partir de config.sh (tableau SHARES),
# recrée les comptes Samba et (re)démarre les services.
# =============================================================================

configure_samba() {
  log "Configuration de Samba..."

  # ------------------------------------------------------------------
  # 1. Sauvegarde de l'ancienne configuration
  # ------------------------------------------------------------------
  if [[ -f /etc/samba/smb.conf ]]; then
    local backup="/etc/samba/smb.conf.bak.$(date +%Y%m%d_%H%M%S)"
    cp /etc/samba/smb.conf "$backup"
    ok "Sauvegarde : $backup"
  fi

  # ------------------------------------------------------------------
  # 2. Section [global]
  # ------------------------------------------------------------------
  local hostname_upper
  # NetBIOS name is limited to 15 characters
  hostname_upper=$(hostname -s | tr '[:lower:]' '[:upper:]' | cut -c1-15)

  cat > /etc/samba/smb.conf << EOF
# Généré par samba.sh — ne pas modifier manuellement
# Dernière mise à jour : $(date '+%Y-%m-%d %H:%M:%S')

[global]
    workgroup       = WORKGROUP
    server string   = HMD Serveur de Fichiers
    netbios name    = ${hostname_upper}

    # Sécurité
    security        = user
    map to guest    = bad user
    # Connexions anonymes mappées sur le compte Linux 'guest'
    guest account   = guest

    # Encodage
    unix charset    = UTF-8
    dos charset     = CP850

    # Journalisation
    log file        = /var/log/samba/log.%m
    max log size    = 5000
    log level       = 1 auth:3

    # Performances
    socket options  = TCP_NODELAY IPTOS_LOWDELAY
    use sendfile    = yes

    # ACL POSIX <-> ACL Windows
    vfs objects         = acl_xattr
    map acl inherit     = yes
    store dos attributes = yes

    # Masque les dossiers/fichiers que l'utilisateur ne peut pas lire :
    # avec le partage racine HMD, chacun ne voit que ses dossiers autorises.
    hide unreadable     = yes

    # Résolution de noms (maître local)
    local master    = yes
    preferred master = yes
    os level        = 65
    wins support    = no
    dns proxy       = no

EOF

  # ------------------------------------------------------------------
  # 3. Sections de partage (générées depuis le tableau SHARES)
  # ------------------------------------------------------------------
  local entry name rel valid_users_str abs_path guest_ok valid_users_smb

  for entry in "${SHARES[@]}"; do
    IFS='|' read -r name rel valid_users_str <<< "$entry"
    if [[ "$rel" == "." || -z "$rel" ]]; then
      abs_path="${HMD_ROOT}"
    else
      abs_path="${HMD_ROOT}/${rel}"
    fi

    # valid users -> "@hmd_comptable @hmd_admin ..."
    valid_users_smb="$(resolve_valid_users "$valid_users_str") @$(resolve_group admin)"
    # Déduplication (admin peut déjà être inclus via le profil)
    valid_users_smb=$(echo "$valid_users_smb" | tr ' ' '\n' | sort -u | tr '\n' ' ' | sed 's/ $//')

    # guest ok = yes si le jeton ALL est présent (le partage est public)
    if [[ "$valid_users_str" == *"ALL"* ]]; then
      guest_ok="yes"
    else
      guest_ok="no"
    fi

    cat >> /etc/samba/smb.conf << EOF
[${name}]
    path            = ${abs_path}
    comment         = HMD — ${name}
    browseable      = yes
    read only       = no
    guest ok        = ${guest_ok}
    valid users     = ${valid_users_smb}
    create mask     = 0660
    force create mode = 0660
    directory mask  = 0770
    force directory mode = 0770
    inherit acls    = yes

EOF
  done

  # ------------------------------------------------------------------
  # 4. Validation de la configuration
  # ------------------------------------------------------------------
  if ! testparm -s >/dev/null 2>&1; then
    err "La configuration Samba générée est invalide !"
    err "Vérifiez /etc/samba/smb.conf"
    return 1
  fi
  ok "smb.conf écrit et validé par testparm."

  # ------------------------------------------------------------------
  # 5. (Re)démarrage des services
  # ------------------------------------------------------------------
  systemctl enable smbd nmbd >/dev/null 2>&1
  systemctl restart smbd nmbd
  ok "Services smbd / nmbd redémarrés."

  # Ouvrir le pare-feu si UFW est actif
  if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow samba >/dev/null
    ok "Règles UFW pour Samba ajoutées."
  fi

  # ------------------------------------------------------------------
  # 6. Comptes Samba (mots de passe initiaux)
  # ------------------------------------------------------------------
  _set_samba_passwords

  local ip
  ip=$(hostname -I | awk '{print $1}')
  log ""
  log "Partages disponibles depuis Windows :"
  for entry in "${SHARES[@]}"; do
    IFS='|' read -r name _ _ <<< "$entry"
    log "   \\\\${ip}\\${name}"
  done
}

# ------------------------------------------------------------------------------
_set_samba_passwords() {
  log "Initialisation des mots de passe Samba..."

  : > "$SMB_CRED_FILE"
  chmod 600 "$SMB_CRED_FILE"
  printf '# Mots de passe Samba initiaux HMD — %s\n' "$(date)" >> "$SMB_CRED_FILE"
  printf '# Changez-les immédiatement : smbpasswd <login>\n\n' >> "$SMB_CRED_FILE"

  local entry login profile pwd
  for entry in "${USERS[@]}"; do
    IFS=':' read -r login profile _ _ <<< "$entry"

    # Le compte 'guest' est anonyme, pas de mot de passe Samba
    [[ "$login" == "guest" ]] && continue

    # Idempotent : ne recrée pas si le compte existe déjà
    if pdbedit -u "$login" >/dev/null 2>&1; then
      ok "Compte Samba existant conservé : $login"
      continue
    fi

    # dd lit un bloc fixe -> évite SIGPIPE avec set -o pipefail
    pwd=$(dd if=/dev/urandom bs=128 count=1 2>/dev/null | tr -dc 'A-Za-z0-9@#%!' | cut -c1-16)
    printf '%s\n%s\n' "$pwd" "$pwd" | smbpasswd -a -s "$login"
    printf '%-15s : %s\n' "$login" "$pwd" >> "$SMB_CRED_FILE"
    ok "Compte Samba créé : $login"
  done

  ok "Mots de passe initiaux stockés dans : $SMB_CRED_FILE (visible root seulement)"
  warn "→ Lire les mots de passe :   cat $SMB_CRED_FILE"
  warn "→ Changer un mot de passe :  smbpasswd <login>"
}
