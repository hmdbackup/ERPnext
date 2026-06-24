#!/usr/bin/env bash
# =============================================================================
# config.sh — Données de configuration du serveur de fichiers HMD
# -----------------------------------------------------------------------------
# C'est la SEULE source de vérité. Modifiez ce fichier (utilisateurs,
# arborescence, permissions) sans toucher à la logique (setup.sh / samba.sh /
# test.sh). Tous les scripts re-dérivent leur comportement d'ici.
# =============================================================================

# Racine des données (le « Root » de l'arborescence).
# Correspond au répertoire existant sur le serveur.
HMD_ROOT="${HMD_ROOT:-/home/hmd/partage_windows}"

# Préfixe de namespace pour les groupes (évite toute collision avec des
# groupes système existants : admin, users, etc.)
GP="hmd"

# --- Groupes de profil -------------------------------------------------------
# Pour chaque profil <p>, le groupe Linux créé sera : ${GP}_<p>
# (ex: admin -> hmd_admin, comptable -> hmd_comptable, ...)
# NB: « gestionnaire » est créé mais reste VIDE (aucun utilisateur ne l'a
#     dans votre liste) : il est prêt pour un usage futur.
PROFILE_GROUPS=(admin comptable gestionnaire elevage vegetale fromagerie guest)

# Groupes agrégés (gérés automatiquement) :
GRP_ALL="${GP}_all"       # « All »        = TOUS les utilisateurs (Guest inclus)
GRP_STAFF="${GP}_staff"   # « All - Guest » = tous SAUF les Guests

# --- Utilisateurs ------------------------------------------------------------
# Format : "login:profil:Nom complet:shell"
#   profil ∈ PROFILE_GROUPS
#   shell  : bash    -> compte interactif (admin, accède en SSH)
#            nologin -> accès fichiers (Samba) uniquement, pas de session shell
USERS=(
  "samir:admin:Samir:bash"
  "aziz:admin:Aziz:bash"
  "anissa:comptable:Anissa:nologin"
  "amen_allah:elevage:Amen Allah:nologin"
  "siwar:elevage:Siwar:nologin"
  "yassine:vegetale:Yassine:nologin"
  "tawfiq:fromagerie:Tawfiq:nologin"
  "ridha:guest:Ridha:nologin"
  "guest:guest:Guest:nologin"
)

# --- Arborescence + permissions ---------------------------------------------
# Format : "chemin relatif|lecture|ecriture"
#   - lecture / ecriture : liste de profils séparés par des virgules.
#   - Tokens spéciaux : ALL = tous (Guest inclus), STAFF = tous sauf Guest.
#   - Champ vide = personne via ce mécanisme.
#   - RÈGLE GLOBALE : l'admin a TOUJOURS rwx partout (ajouté automatiquement).
#   - "lecture" accorde r-x (lister + entrer). "ecriture" accorde rwx.
#   - "." = la racine HMD_ROOT elle-même.
#
# Les chemins correspondent à la structure existante sur le serveur (minuscules).
DIRS=(
  ".|ALL|"                                      # Racine : tout le monde liste les sections

  # ----- Support (administratif / finance) -----
  "support|comptable,gestionnaire|"             # liste réservée compta + gestion (admin rwx)
  "support/administratif|comptable,gestionnaire|comptable"
  "support/comptabilite|comptable,gestionnaire|comptable"
  "support/rh|comptable,gestionnaire|comptable"
  "support/gestion|comptable,gestionnaire|gestionnaire"
  "support/divers|comptable,gestionnaire|comptable,gestionnaire"
  "support/dropbox|ALL|ALL"

  # ----- Elevage (= Resp. Prod. Animale) -----
  "elevage|STAFF|elevage"
  "elevage/bovin|STAFF|elevage"
  "elevage/ovin|STAFF|elevage"
  "elevage/dropbox|ALL|ALL"

  # ----- Fromagerie -----
  "fromagerie|STAFF|fromagerie"
  "fromagerie/dropbox|ALL|ALL"

  # ----- Production Végétale -----
  "production_vegetale|STAFF|vegetale"
  "production_vegetale/borj_essebi|STAFF|vegetale"
  "production_vegetale/borj_essebi/grandes_cultures|STAFF|vegetale"
  "production_vegetale/borj_essebi/oliviers|STAFF|vegetale"
  "production_vegetale/borj_essebi/irrigue|STAFF|vegetale"
  "production_vegetale/tahoura|STAFF|vegetale"
  "production_vegetale/henchir_gouia|STAFF|vegetale"
  "production_vegetale/dropbox|ALL|ALL"

  # ----- IT -----
  "it|STAFF|"                                   # liste pour le staff (admin rwx)
  "it/back-up|admin|admin"                      # admin seulement, lecture + écriture
  "it/software|ALL|admin"
  "it/dropbox|ALL|ALL"

  # ----- Utilisateurs (dossiers personnels générés depuis USERS) -----
  "utilisateurs|ALL|"                           # tout le monde traverse vers son dossier
  "utilisateurs/partage|ALL|ALL"
)

# --- Dossiers à rendre TRAVERSABLES par tous (--x) ---------------------------
# Ces dossiers ont une LECTURE restreinte, mais contiennent en dessous un
# DropBox / Software « All » que TOUT LE MONDE (Guest inclus) doit pouvoir
# atteindre. On accorde donc seulement le droit de TRAVERSÉE (--x) à hmd_all :
# on peut « passer à travers » sans pouvoir LISTER le contenu du dossier parent.
TRAVERSE_ALL_DIRS=(
  "support"
  "elevage"
  "fromagerie"
  "production_vegetale"
  "it"
)

# --- Partages Samba ----------------------------------------------------------
# Format : "NomPartage|chemin relatif|utilisateurs autorisés"
#   - utilisateurs autorisés : tokens (ALL/STAFF/profil) -> traduits en @groupe.
#   - C'est une défense en profondeur : la sécurité réelle vient des ACL.
#   - Les partages « Depot-* » pointent directement sur les DropBox « All » :
#     ils permettent aux Guests d'y accéder sans parcourir le dossier parent.
SHARES=(
  # Partage RACINE : un seul lecteur monte toute l'arborescence. Les ACL +
  # « hide unreadable » font que chaque utilisateur ne VOIT que ce qu'il peut
  # ouvrir. Reserve au staff+admin (les invites passent par Partage/Depot-*).
  "HMD|.|STAFF,admin"

  "Support|support|comptable,gestionnaire,admin"
  "Elevage|elevage|STAFF,admin"
  "Fromagerie|fromagerie|STAFF,admin"
  "Production_Vegetale|production_vegetale|STAFF,admin"
  "IT|it|STAFF,admin"
  "Utilisateurs|utilisateurs|ALL"
  "Partage|utilisateurs/partage|ALL"
  "Depot-Support|support/dropbox|ALL"
  "Depot-Elevage|elevage/dropbox|ALL"
  "Depot-Fromagerie|fromagerie/dropbox|ALL"
  "Depot-Vegetale|production_vegetale/dropbox|ALL"
  "Depot-IT|it/dropbox|ALL"
  "Logiciels|it/software|ALL"
)

# Fichier où seront écrits les mots de passe Samba initiaux (root uniquement).
SMB_CRED_FILE="${SMB_CRED_FILE:-/root/hmd-smb-credentials.txt}"
