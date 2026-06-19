# HMD AGRO

Custom dairy farm management system for HMD AGRO — animal management, milk production tracking, feeding, reproduction, and health monitoring.

---

## Self-Host with Docker

Deploy HMD Agro (ERPNext v15 + custom app) using Docker on any platform.

### Prerequisites

| Requirement       | Minimum              |
| ----------------- | -------------------- |
| RAM               | 4 GB                 |
| Disk              | 10 GB                |
| Docker            | 24+                  |
| Docker Compose    | v2 (built into Docker) |
| Ports             | 80 / 443 open        |

#### Install Docker

<details>
<summary><b>Linux (Ubuntu)</b></summary>

```bash
# Remove old packages
sudo apt-get remove docker docker-engine docker.io containerd runc

# Install prerequisites
sudo apt-get update && sudo apt-get install -y \
  ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine, Compose plugin, and BuildKit
sudo apt-get update && sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start Docker and enable on boot
sudo systemctl enable docker --now

# Add your user to the docker group (no sudo needed after re-login)
sudo usermod -aG docker $USER
newgrp docker
```

Verify: `docker --version && docker compose version`

</details>

<details>
<summary><b>macOS</b></summary>

1. Download **Docker Desktop for Mac** from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
2. Open the `.dmg` and drag Docker into `Applications`
3. Launch Docker Desktop (you may need to approve it in **System Preferences → Security & Privacy**)
4. Docker Compose v2 is included — no separate install needed

Alternatively via [Homebrew](https://brew.sh):

```bash
brew install --cask docker
```

Then launch Docker Desktop from Applications.

Verify: `docker --version && docker compose version`

</details>

<details>
<summary><b>Windows</b></summary>

1. Enable **WSL 2** (required for Docker Desktop):
   ```powershell
   # Run as Administrator in PowerShell
   wsl --install
   ```
2. Restart your machine.
3. Download **Docker Desktop for Windows** from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)
4. Run the installer and ensure **Use WSL 2 instead of Hyper-V** is selected
5. Launch Docker Desktop
6. In **Settings → Resources → WSL Integration**, enable integration with your WSL distro

Docker Compose v2 is included — no separate install needed.

> **Note:** All commands below should be run in **WSL 2 terminal** (Ubuntu) for best compatibility, or in PowerShell with `bash` (shipped with Git for Windows).

Verify: `docker --version && docker compose version`

</details>

---

### Deploy (all platforms)

**1. Clone repos**

```bash
git clone https://github.com/frappe/frappe_docker
git clone -b main https://github.com/Mouh1b/hmd_agro
cd frappe_docker
```

**2. Overlay HMD-specific files**

```bash
cp ../hmd_agro/deploy/apps.json ../hmd_agro/deploy/.env.hmd ../hmd_agro/deploy/build-hmd.sh .
```

**3. Build the custom image**

```bash
bash build-hmd.sh --no-cache
```

**4. Configure environment**

```bash
cp .env.hmd .env
```

Edit `.env` and set at minimum:
- `DB_PASSWORD` — strong random password
- `LETSENCRYPT_EMAIL` — your email for SSL certificates
- `SITES_RULE` — e.g. `Host(\`hmd.agro\`)` or `Host(\`hmd-prod.local\`)` for local testing

**5. Start the stack**

```bash
docker compose --env-file .env up -d
sleep 30
docker compose ps
```

All 7 containers should show `running`.

**6. Create the site**

```bash
docker compose exec backend bench new-site hmd.agro \
  --mariadb-user-host-login-scope=% \
  --db-root-password YOUR_DB_PASSWORD \
  --admin-password CHANGE_ME \
  --install-app erpnext
```

**7. Install HMD Agro**

```bash
docker compose exec backend bench --site hmd.agro install-app hmd_agro
```

**8. Open** `https://<your-domain>` and log in as `Administrator`. Change the password on first login.

---

### Local testing (no real domain)

Add to your hosts file:

| Platform | File |
| -------- | ---- |
| Linux / Mac | `/etc/hosts` |
| Windows | `C:\Windows\System32\drivers\etc\hosts` |

```
127.0.0.1 hmd-prod.local
```

In `.env`, set:

```
SITES_RULE=Host(`hmd-prod.local`)
FRAPPE_SITE_NAME_HEADER=hmd.agro
```

Recreate the stack:

```bash
docker compose --env-file .env up -d --force-recreate
```

Visit `https://hmd-prod.local` (accept the self-signed SSL warning).

---

### Updates

```bash
# After pulling new code
bash build-hmd.sh
docker compose --env-file .env up -d
docker compose exec backend bench --site hmd.agro migrate
```

---

### Backups

Automatic every 6 hours (stored in `sites/hmd.agro/private/backups`).

Manual backup:
```bash
docker compose exec backend bench --site hmd.agro backup --with-files
```

---

### Reset everything

```bash
docker compose --env-file .env down -v
docker image rm hmd-agro-prod:v15 2>/dev/null || true
docker system prune -af --volumes
```

---

## Development Installation (bench)

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/Mouh1b/hmd_agro --branch main
bench install-app hmd_agro
```

---

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/hmd_agro
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

---

## License

MIT
