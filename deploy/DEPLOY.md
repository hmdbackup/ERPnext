# HMD Agro — Production Deployment

## Requirements

- Docker + Docker Compose
- Public domain pointing to the server (skip if testing locally — see *Local Test* below)
- Ports `80` / `443` open
- ~4 GB RAM, ~10 GB disk

---

## Deploy from a fresh machine

**1.** Clone both repos as siblings, then enter `frappe_docker`.
```bash
git clone https://github.com/frappe/frappe_docker
git clone -b main https://github.com/Mouh1b/hmd_agro hmd_agro
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

**App code change** — push to `Mouh1b/hmd_agro` (main), then on the server:
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
- `apps.json` pulls hmd_agro from a public repo. For private, pass a GitHub token as a build arg.
- On Windows, `bash` ships with Git for Windows.
- Full reference: [`frappe_docker/docs/`](https://github.com/frappe/frappe_docker/tree/main/docs).
