# Rattrapage des fichiers serveur vers le dépôt

Prompt à coller dans Claude Code **sur hmdsecour (192.168.1.3)**, dans `/home/hmd/GestionBackup`. Ce poste a l'accès SSH à .4 et les dossiers de travail.

---

Objectif : rapatrier dans le dépôt GitHub `hmdbackup/ERPnext`, branche `claude/ubuntu-fsck-logs-ram-ewtalc` (PR #2), tous les scripts et toute la documentation d'infrastructure HMD qui sont sur les serveurs mais pas dans le dépôt. **Aucun secret ne doit être commité.**

1. Clone : `git clone -b claude/ubuntu-fsck-logs-ram-ewtalc https://github.com/hmdbackup/ERPnext ~/ERPnext-sync`
2. Inventaire, en lecture seule, comparé à ce qui est déjà dans `deploy/`, `infra/hmd-fileserver/` et `infra/hmd-server/` :
   - .3 : `/home/hmd/GestionBackup/hmd-backup-restore/` (dépôt local de 3 commits non poussés : README, `docs/BACKUP.md`, `docs/RESTORE.md`, `serveur-principal/`, `serveur-secours/`), `/home/hmd/GestionBackup/restauration/hmd-restore/`, `/opt/hmd-restore/`, `/etc/systemd/system/hmd-restore.*`
   - .4 (`ssh hmd@192.168.1.4`) : `/opt/hmd-backup/` (sans `credentials/`), `/etc/systemd/system/hmd-backup-*`, `/etc/ssh/sshd_config.d/99-hmd-keepalive.conf`, la configuration Samba des partages (`/etc/samba/smb.conf`), l'overlay `frappe_docker` réellement déployé (`apps.json`, `build-hmd.sh`, Containerfile patché, `.env` **sans les valeurs secrètes**)
   - Pour chaque fichier, comparer la version en service (`/opt/...`) avec la copie de travail, et garder la version **en service**. Lister les écarts.
3. Placement :
   - `infra/hmd-backup/serveur-principal/`, `infra/hmd-backup/serveur-secours/`, `infra/hmd-backup/docs/` ;
   - les unités systemd dans `systemd/` à côté de leurs scripts ;
   - les configurations sous forme `*.example` : `backup.conf.example`, `restore.conf.example`, `.env.example`, avec les valeurs secrètes remplacées par `REMPLACER_PAR_...`.
4. **Interdits** : `credentials/`, `gmail.env`, `rclone.conf`, `aws-*`, `archive-passphrase`, `*.json` de compte de service, clés SSH (`id_*`), `*.gpg`, `*.tdb`, logs, `HMD_BACKUPS/`, mots de passe dans `.env` ou `backup.conf`. Avant de commiter : `git diff --cached | grep -iE 'passw|secret|token|AKIA|BEGIN .*PRIVATE|app_password|refresh_token'` ne doit rien renvoyer, sauf des emplacements `REMPLACER_PAR`.
5. Garder l'historique utile : `git subtree` ou un commit unique qui cite les 3 commits locaux d'origine.
6. Commit, puis `git push origin claude/ubuntu-fsck-logs-ram-ewtalc`.
7. Rapport attendu : liste des fichiers ajoutés, écarts entre la version en service et la copie de travail, fichiers volontairement exclus.
