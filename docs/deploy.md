# Deploying March Madness

Deploy the dashboard and API to a single cloud VPS. The recommended path uses **Docker**; a **bare-metal** option (Python + Node + Nginx on the host) is also supported.

## Where to run

Use any Linux VPS with SSH and a public IP (or domain pointing to it):

- **DigitalOcean** — Create a Droplet (Ubuntu 22.04), add your SSH key, note the IP.
- **Hetzner** — Create a CX/CPX instance (Ubuntu), add SSH key, note the IP.
- **Linode / Akamai** — Create a Linode (Ubuntu), add SSH key, note the IP.
- **AWS EC2** — Launch an Ubuntu AMI, open ports 22, 80, 443 in the security group, note the public IP.
- **Azure** — Create an Ubuntu VM, open 22, 80, 443 in the NSG, note the public IP.

## One-time bootstrap (Docker path)

Before the first deploy, clone the repo on the VPS and install Docker. The deploy workflow does **not** clone for you; it assumes the app dir already exists and runs `git pull` before rebuilding.

On the VPS:

1. **Install Docker and Docker Compose** (e.g. [Docker’s install script](https://docs.docker.com/engine/install/) for Ubuntu).

2. **Clone the repo** (or copy it) to a directory, e.g. `/var/www/march-madness`:
   ```bash
   sudo mkdir -p /var/www
   sudo chown "$USER" /var/www
   git clone https://github.com/YOUR_USER/march-madness.git /var/www/march-madness
   cd /var/www/march-madness
   ```
   Clone creates `data/raw` and `data/processed` (with `.gitkeep`). The repo may include `data/raw/bracket_2026.json`; if not, add it (see Data on the server below).

3. **Data on the server** — The app needs bracket and (optionally) Kaggle data on the server. Data and model artifacts are not in git.
   - Ensure `data/raw/bracket_2026.json` exists (it may be committed; if not, copy it into `data/raw/`).
   - Optionally add Kaggle CSVs to `data/raw/` for full model training and history features.
   - Run refresh once (step 6) so the API can serve the dashboard; refresh writes cache and matchup matrix into `data/processed/`. The `data/processed/` directory must be writable by the user running Docker or the API.

4. **Build the frontend** and put it in `frontend-dist/` (or let CI do this on first deploy; the workflow rsyncs the built frontend into `frontend-dist/`):
   ```bash
   cd dashboard/frontend && npm ci && npm run build
   cd ../.. && cp -r dashboard/frontend/dist/* frontend-dist/
   ```

5. **Start the stack**:
   ```bash
   docker compose up -d
   ```
   The app is served on port 80. The API is available at `/api` (e.g. `/api/bracket`).

6. **Run refresh once** so the dashboard has bracket cache and matchup matrix:
   ```bash
   docker compose --profile tools run --rm refresh
   ```
   If you see “No bracket file”, add `data/raw/bracket_2026.json` and run again.

## Deploy flow (CI/CD)

- **CI** (`.github/workflows/ci.yml`): on every push/PR to `main`, runs tests and builds the frontend.
- **Deploy** (`.github/workflows/deploy.yml`): on push to `main`, builds the frontend, rsyncs it to the VPS `frontend-dist/`, SSHs in and runs `docker compose build api && docker compose up -d`.

**Secrets** (Settings → Secrets and variables → Actions):

- `SSH_PRIVATE_KEY` — Private key for SSH (no passphrase, or use an agent).
- `VPS_HOST` — VPS IP or hostname.
- Optional: `VPS_USER` (default `root`), `VPS_APP_DIR` (default `/var/www/march-madness`).

The server must have the repo cloned and Docker installed (one-time bootstrap above).

## Refresh flow

Refresh regenerates the bracket cache and matchup matrix (so the dashboard and what-if stay correct after data or bracket changes).

- **Docker**: On the VPS, run:
  ```bash
  cd /var/www/march-madness
  docker compose --profile tools run --rm refresh
  ```
- **GitHub Actions**: Use the **Refresh** workflow (Actions → Refresh → Run workflow). It SSHs to the VPS and runs the same refresh (Docker or bare-metal venv). You can enable the schedule in `.github/workflows/refresh.yml` for a daily run.

## Bare-metal (no Docker)

1. Install Python 3.10+, Node, Nginx on the server.
2. Clone the repo to e.g. `/var/www/march-madness`, create `.venv`, `pip install -e .`, create `data/raw` and `data/processed`.
3. Install the systemd unit: copy `deploy/systemd/march-madness-api.service` and adjust paths; enable and start the service.
4. Install Nginx: use `deploy/nginx-bare.conf` (proxy to `127.0.0.1:8000`), set `root` to the path where you put the built frontend (e.g. `/var/www/march-madness/frontend-dist`).
5. Build frontend: `cd dashboard/frontend && npm run build && cp -r dist/* ../../frontend-dist/`.
6. Deploy script: run `./deploy/scripts/deploy.sh` (from repo root) to reinstall deps, rebuild frontend, and restart the API. Refresh: `./deploy/scripts/refresh.sh`.

## Custom subdomain (e.g. mm.adamolson.org)

If you own a domain (e.g. **adamolson.org**) on another host and want the app at **mm.adamolson.org**:

### 1. Add a DNS record

Wherever **adamolson.org** is managed (GoDaddy, Namecheap, Cloudflare, Google Domains, Route 53, etc.):

- **Type:** `A`
- **Name/host:** `mm` (or `mm.adamolson` depending on the provider; you want the FQDN to be `mm.adamolson.org`)
- **Value:** Your VPS public IP (the same IP you use for SSH and that you set as `VPS_HOST` in GitHub Actions)
- **TTL:** 300 or 3600

Save the record. DNS can take a few minutes to an hour to propagate. Check with `dig mm.adamolson.org` or [whatsmydns.net](https://www.whatsmydns.net/#A/mm.adamolson.org).

### 2. Use the domain in Nginx (Docker)

So the app responds to `http://mm.adamolson.org` instead of only the IP:

- Copy the domain Nginx config and use it for the web container: `cp deploy/nginx-domain.conf deploy/nginx.conf` (or mount `nginx-domain.conf` as the default in `docker-compose.yml`). It has `server_name mm.adamolson.org`. Redeploy so the container picks up the config.
- Optional: set GitHub Actions secret `VPS_HOST` to `mm.adamolson.org` so deploy and refresh use the hostname.

### 3. HTTPS (recommended for a public URL)

The stack is HTTP-only. To serve **https://mm.adamolson.org** with a free certificate:

**Option A — Certbot on the VPS (Nginx on host)**  
Put Nginx and certbot on the host; run the app container on an internal port so the host can bind 80/443.

1. In `docker-compose.yml`, change the web service ports from `"80:80"` to `"8080:80"`.
2. On the VPS, install Nginx and certbot: `sudo apt install nginx certbot python3-certbot-nginx`.
3. Use the example host config: `deploy/nginx-host-ssl.conf.example`. Copy it to e.g. `/etc/nginx/sites-available/mm.adamolson.org`. Edit so the proxy target is `http://127.0.0.1:8080`.
4. For the first run, use a temporary server block that listens on 80, serves `/.well-known/acme-challenge/` from `/var/www/certbot`, and proxies everything else to `http://127.0.0.1:8080`. Run: `sudo certbot certonly --webroot -w /var/www/certbot -d mm.adamolson.org`.
5. Then switch to the full config in the example (redirect HTTP to HTTPS and 443 with `ssl_certificate` from certbot). Run `sudo nginx -t && sudo systemctl reload nginx`.
6. Set `CORS_ORIGINS=https://mm.adamolson.org` for the API (see Troubleshooting). Renewal: `sudo certbot renew` (or use a systemd timer/cron).

**Option B — Caddy in front**  
Run Caddy in a container or on the host with `CADDY_DOMAIN=mm.adamolson.org`; it obtains and renews Let's Encrypt certs automatically.

After HTTPS is working, set `CORS_ORIGINS=https://mm.adamolson.org` in the API environment.

---

## HTTPS (for public sharing)

The stack serves HTTP only. For a public URL you should add HTTPS. Two common options: (1) **On the VPS** — Put Caddy or Nginx in front with Let’s Encrypt (e.g. `certbot` and an Nginx config for TLS). (2) **In the cloud** — Use a load balancer (e.g. AWS ALB, Azure Load Balancer) with an ACM/Key Vault certificate and terminate TLS there, forwarding HTTP to the VPS. After HTTPS is in place, set `CORS_ORIGINS` to your `https://` origin (see Troubleshooting).

## Troubleshooting

- **503 or “Bracket cache missing”** — The API serves `/bracket` only from prebuilt cache. Run refresh (Docker: `docker compose --profile tools run --rm refresh`; bare metal: `./deploy/scripts/refresh.sh` or `PYTHONPATH=src python scripts/refresh.py`). Ensure `data/raw/bracket_2026.json` exists and, if needed, Kaggle data is in `data/raw/`.
- **Blank or “Frontend not built”** — Build the frontend and copy `dashboard/frontend/dist/*` into `frontend-dist/` (Docker) or the Nginx `root` (bare metal).
- **API not reachable** — Check that the reverse proxy forwards `/api/` to the API (Docker: `api:8000`; bare metal: `127.0.0.1:8000`). The frontend uses same-origin `/api` by default; do not point it at `localhost:8000` in production.

**CORS** — For production with a public URL, restrict CORS to your frontend origin. Set `CORS_ORIGINS` to a comma-separated list (e.g. `https://yourdomain.com`). Docker: add `environment: - CORS_ORIGINS=https://yourdomain.com` to the `api` service in `docker-compose.yml`. Bare metal: set the env var in the systemd unit or shell. If unset, the API allows all origins (fine for local/dev).
