# HMD Agro — Setup & Deployment Guide

> Covers (A) developing on your own laptop via the VS Code dev container, and
> (B) deploying to production on the farm server. New interns: do **part A** first.

## Requirements (production — part B)

- Docker + Docker Compose
- Public domain pointing to the server (skip if testing locally — see *Local Test* below)
- Ports `80` / `443` open
- ~4 GB RAM, ~10 GB disk

---

This guide has two parts:
- **A) Develop on your own machine** — the VS Code dev container, for editing code and testing at `http://hmd.localhost:8000`. **Start here if you're a new intern.**
- **B) Deploy to production** — build the Docker image and run it live on the farm server.

---

# A) Develop on your own machine (VS Code dev container)

### Prerequisites
- **Docker Desktop** (give it ≥ 4 GB RAM in Settings → Resources)
- **VS Code** + the **Dev Containers** extension (`ms-vscode-remote.remote-containers`)
- **Git**

### Steps (run on your laptop)

**1.** Clone `frappe_docker` and set up the dev-container config.
```bash
# --config core.autocrlf=false is CRITICAL on Windows (otherwise containers crash-loop on CRLF)
git clone --config core.autocrlf=false https://github.com/frappe/frappe_docker
cd frappe_docker
cp -R devcontainer-example .devcontainer
cp -R development/vscode-example development/.vscode
```

**2.** Open the folder in VS Code and start the container.
```bash
code .
```
Then: Command Palette (`Ctrl+Shift+P`) → **Dev Containers: Reopen in Container**. Wait for it to build (first time is slow). This starts the `frappe`, `mariadb`, `redis-cache`, `redis-queue` containers.

**3.** Open a terminal **inside the container** (it should say user `frappe`) and create the bench. Everything below runs inside the container.
```bash
bench init --skip-redis-config-generation --frappe-branch version-15 frappe-bench
cd frappe-bench
```

**4.** Point bench at the service containers (not localhost).
```bash
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
```

**5.** Fetch the apps. ERPNext first, then HMD Agro.
```bash
bench get-app --branch version-15 --resolve-deps erpnext
# The repo is named ERPnext but the app is hmd_agro — passing "hmd_agro" first
# forces the local app folder to be named hmd_agro:
bench get-app hmd_agro --branch main https://github.com/hmdbackup/ERPnext
```

**6.** Create the dev site (`.localhost` is required for local use). MariaDB root password default is `123`.
```bash
bench new-site --mariadb-user-host-login-scope=% --db-root-password 123 --admin-password admin hmd.localhost
```

**7.** Install both apps on the site.
```bash
bench --site hmd.localhost install-app erpnext
bench --site hmd.localhost install-app hmd_agro
```

**8.** Turn on developer mode and select the site.
```bash
bench --site hmd.localhost set-config developer_mode 1
bench --site hmd.localhost clear-cache
bench use hmd.localhost
```

**9.** (Optional) Import the farm data — see the import guide (`farm_data/` CSVs + the `setup/import_*.py` scripts). The CSVs are NOT in git, so copy them in first.

**10.** Start everything.
```bash
bench start
```
Open **`http://hmd.localhost:8000`** → log in as `Administrator` / `admin`.

> After editing Python you usually need `bench --site hmd.localhost clear-cache` (and restart `bench start`); page JS just needs a hard refresh (`Ctrl+Shift+R`). After changing a DocType, run `bench --site hmd.localhost migrate`.

---

# B) Deploy to production

## Deploy from a fresh machine

**1.** Clone both repos as siblings, then enter `frappe_docker`.
```bash
git clone https://github.com/frappe/frappe_docker
# repo is named ERPnext but the app is hmd_agro → clone INTO a folder named hmd_agro
git clone -b main https://github.com/hmdbackup/ERPnext hmd_agro
cd frappe_docker
```

**2.** Overlay the HMD-specific files.
```bash
cp ../hmd_agro/deploy/apps.json ../hmd_agro/deploy/.env.hmd ../hmd_agro/deploy/build-hmd.sh .
```

**3.** Build the custom image (no cache → guaranteed fresh).
```bash
bash build-hmd.sh --no-cache
```

**4.** Create the environment file and edit it.
```bash
cp .env.hmd .env
nano .env
```
Set at least: `DB_PASSWORD`, `LETSENCRYPT_EMAIL`, `SITES_RULE`.

**5.** Launch the stack.
```bash
docker compose --env-file .env up -d
sleep 30
docker compose ps
```
All 7 containers should show `running`.

**6.** Create the site (replace `YOUR_DB_PASSWORD` with the value from `.env`).
```bash
docker compose exec backend bench new-site hmd.agro \
  --mariadb-user-host-login-scope=% \
  --db-root-password YOUR_DB_PASSWORD \
  --admin-password CHANGE_ME \
  --install-app erpnext
```

**7.** Install the HMD Agro app.
```bash
docker compose exec backend bench --site hmd.agro install-app hmd_agro
```

**8.** Open `https://<your-domain>` and log in as `Administrator`. Change the password.

---

## Reset everything (re-test from scratch)

```bash
cd frappe_docker
docker compose --env-file .env down -v
docker image rm hmd-agro-prod:v15 2>/dev/null || true
docker system prune -af --volumes
```

Then repeat steps 3 → 7. The `down -v` flag destroys data volumes; the system prune frees disk and forces every layer to rebuild from zero.

---

## Updates

**App code change** — push to `hmdbackup/ERPnext` (main), then on the server:
```bash
bash build-hmd.sh
docker compose --env-file .env up -d
docker compose exec backend bench --site hmd.agro migrate
```

**Frappe / ERPNext version change** — edit `ERPNEXT_VERSION` in `.env`, then run the same 3 commands above.

**`frappe_docker` infrastructure update** —
```bash
cd frappe_docker
git pull
docker compose pull
docker compose --env-file .env up -d
```

---

## Backups

Automatic every 6 h via ofelia (`overrides/compose.backup-cron.yaml`). Stored in volume `sites/hmd.agro/private/backups`.

Off-host copy:
```bash
docker compose cp backend:/home/frappe/frappe-bench/sites/hmd.agro/private/backups ./backups
```

Manual one-off backup:
```bash
docker compose exec backend bench --site hmd.agro backup --with-files
```

---

## Local Test (no real domain)

For laptop demo without public DNS:

**1.** Add to hosts file (`C:\Windows\System32\drivers\etc\hosts` or `/etc/hosts`):
```
127.0.0.1 hmd-prod.local
```

**2.** In `.env`, set:
```
SITES_RULE=Host(`hmd-prod.local`)
FRAPPE_SITE_NAME_HEADER=hmd.agro
```

**3.** Recreate the stack.
```bash
docker compose --env-file .env up -d --force-recreate
```

**4.** Visit `https://hmd-prod.local` (accept self-signed SSL warning).

The `FRAPPE_SITE_NAME_HEADER` override tells Frappe to serve the internal `hmd.agro` site regardless of the URL host.

---

## Notes

- `.env` is not committed — only `.env.hmd` (template) is tracked.
- `apps.json` pulls the hmd_agro app from the public repo `hmdbackup/ERPnext` (branch `main`). The repo name differs from the app name — bench reads the app name (`hmd_agro`) from the code, so the build is unaffected.
- On Windows, `bash` ships with Git for Windows.
- Full reference: [`frappe_docker/docs/`](https://github.com/frappe/frappe_docker/tree/main/docs).
