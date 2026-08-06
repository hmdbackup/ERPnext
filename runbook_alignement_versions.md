# Runbook — Alignement des versions (production, utilisateurs, benches de dev)

> Destinataires : **Aziz** (serveur de production), **Siwar / Soumaya** (utilisatrices),
> et les développeurs. Coordinateur : **Mohamed Slim**.

## Pourquoi le site était en retard de 2 mois (cause racine, en 5 lignes)

1. L'image de production est construite depuis `deploy/apps.json`, qui tire `hmd_agro` depuis la branche `main` de `hmdbackup/ERPnext`.
2. Or tout le travail finance (Epics A → H, 10 commits) est resté sur la branche `finance/socle-comptable` : le dernier commit de `main` date du 30/06/2026 → la production embarque forcément du code vieux de 2 mois.
3. En plus, le script de build utilisait le cache Docker : même après un push, une couche `git clone` en cache pouvait resservir de l'ancien code.
4. ERPNext était épinglé sur la branche flottante `version-15` (pas un tag exact) : deux builds "identiques" pouvaient contenir des versions ERPNext différentes.
5. Enfin, `hmd_agro.__version__` restait à `0.0.1` : impossible de distinguer les builds dans `bench version` ou dans Aide → À propos.

**Correctifs déjà en place dans le dépôt** : ERPNext épinglé au tag `v15.95.2` dans `deploy/apps.json`, `--no-cache` par défaut dans `deploy/build-hmd.sh`, version applicative montée à `0.2.0`, procédure « Updates » réécrite dans `deploy/DEPLOY.md`.

---

## Étape 0 — Prérequis : fusionner `finance/socle-comptable` dans `main`

> **À faire par Mohamed Slim après validation** (validation fonctionnelle de M. Samir / l'équipe). Ne rien déployer avant cette fusion : sans elle, un rebuild redéploierait le même code obsolète.

```bash
cd /chemin/vers/hmd_agro
git checkout main
git pull origin main
git merge --no-ff finance/socle-comptable -m "Merge finance/socle-comptable (Epics A-H) + alignement versions"
git push origin main
```

En cas de conflit : résoudre, `git add` les fichiers résolus, puis `git commit` et `git push origin main`.

---

## Étape 1 — Serveur de production (Aziz)

Toutes les commandes se lancent dans le dossier `frappe_docker` du serveur.

**1.1 — Relever les versions actuelles (photo « avant »)** :
```bash
docker compose exec backend bench version
docker compose exec backend git -C apps/hmd_agro log -1 --oneline
```
Garder la sortie (copier dans le groupe WhatsApp) — elle sert de preuve de l'état avant/après.

**1.2 — Sauvegarde complète (base + fichiers)** :
```bash
docker compose exec backend bench --site hmd.agro backup --with-files
docker compose cp backend:/home/frappe/frappe-bench/sites/hmd.agro/private/backups ./backups-avant-alignement
```
Vérifier que le dossier `./backups-avant-alignement` contient bien les fichiers `.sql.gz` et `.tar` du jour.

**1.3 — Récupérer les fichiers de déploiement à jour** (après la fusion de l'étape 0) :
```bash
cd ../hmd_agro && git pull origin main && cd ../frappe_docker
cp ../hmd_agro/deploy/apps.json ../hmd_agro/deploy/build-hmd.sh ../hmd_agro/deploy/.env.hmd .
```
(Ne pas écraser le `.env` réel — `.env.hmd` n'est que le modèle.)

**1.4 — Reconstruire l'image SANS cache** (c'est désormais le défaut du script, on le passe quand même explicitement) :
```bash
bash build-hmd.sh --no-cache
```

**1.5 — Recréer les conteneurs** (un simple `up -d` peut garder les anciens) :
```bash
docker compose --env-file .env up -d --force-recreate
docker compose ps   # tous les conteneurs doivent être "running"
```

**1.6 — Migrer le site** :
```bash
docker compose exec backend bench --site hmd.agro migrate
```

**1.7 — Vider les caches serveur** :
```bash
docker compose exec backend bench --site hmd.agro clear-cache
docker compose exec backend bench --site hmd.agro clear-website-cache
```

**1.8 — Vérifier (photo « après »)** :
```bash
docker compose exec backend bench version
# Attendu : erpnext 15.95.2  +  hmd_agro 0.2.0
docker compose exec backend git -C apps/hmd_agro log -1 --oneline
# Attendu : le commit de fusion de l'étape 0
```
Si `hmd_agro` n'affiche pas `0.2.0` ou si le commit n'est pas le bon : le build a réutilisé une couche périmée → refaire 1.4 → 1.8.

Poster la sortie « avant » (1.1) et « après » (1.8) dans le groupe WhatsApp.

---

## Étape 2 — Utilisatrices (Siwar, Soumaya)

Après le feu vert d'Aziz dans le groupe :

1. **Rafraîchissement forcé** du navigateur sur le site : `Ctrl+Shift+R` (un simple F5 ne suffit pas, l'ancien JavaScript peut rester en cache).
2. Ouvrir **Aide (?) → À propos** dans la barre du haut.
3. Vérifier les versions affichées : **ERPNext v15.95.2** et **HMD Agro 0.2.0**. Tout le monde doit voir exactement les mêmes numéros.
4. **Envoyer une capture d'écran** de la fenêtre « À propos » dans le groupe WhatsApp — c'est la confirmation que chacune est bien sur la nouvelle version.

Si les numéros ne correspondent pas : refaire le `Ctrl+Shift+R` ; si ça persiste, vider le cache du navigateur (ou tester en navigation privée) et prévenir Mohamed Slim.

---

## Étape 3 — Benches de développement (développeurs)

Dans le conteneur de dev (dossier `frappe-bench`) :

```bash
# 3.1 — hmd_agro sur main, à jour
cd apps/hmd_agro
git checkout main
git pull origin main

# 3.2 — erpnext sur le tag épinglé v15.95.2 (le même que la production)
cd ../erpnext
git fetch --tags
git checkout v15.95.2

# 3.3 — migrer le site de dev et vérifier
cd ../..
bench --site hmd.localhost migrate
bench --site hmd.localhost clear-cache
bench version
# Attendu : erpnext 15.95.2  +  hmd_agro 0.2.0 (identique à la production)
```

> Note : `git checkout v15.95.2` met erpnext en « detached HEAD » — c'est normal pour un tag épinglé. Pour changer de version ERPNext plus tard, on change d'abord le tag dans `deploy/apps.json` (voir la politique d'épinglage dans `deploy/DEPLOY.md`), puis chaque dev refait le 3.2 avec le nouveau tag.

---

## Règle d'or à retenir

**Une seule source de vérité par version** : `deploy/apps.json` fixe ERPNext (tag exact), la branche `main` + `hmd_agro.__version__` fixent HMD Agro. Tout déploiement suit `deploy/DEPLOY.md` § « Updates » (build `--no-cache` → recreate → migrate → clear caches → vérif `bench version`), et se termine par la vérification « À propos » côté utilisateurs.
