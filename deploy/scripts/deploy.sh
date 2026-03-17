#!/usr/bin/env bash
# Bare-metal deploy: install deps, build frontend, restart API.
# Run from repo root on the server, or set APP_DIR.
# Prereqs: Python venv at .venv, Node for frontend build, nginx and systemd unit installed.
set -e
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$APP_DIR"

echo "Installing Python deps…”
"$APP_DIR/.venv/bin/pip" install -q -e .

echo "Building frontend…"
cd "$APP_DIR/dashboard/frontend"
npm ci --silent
npm run build
mkdir -p "$APP_DIR/frontend-dist"
cp -r dist/* "$APP_DIR/frontend-dist/"

echo "Restarting API…"
sudo systemctl restart march-madness-api.service || true

echo "Done. Frontend at root, API proxied at /api."
