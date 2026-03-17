#!/usr/bin/env bash
# Run refresh on the server (bare metal). From repo root:
#   PYTHONPATH=src ./deploy/scripts/refresh.sh
# Or: cd /var/www/march-madness && PYTHONPATH=src ./deploy/scripts/refresh.sh
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-$ROOT/src}:$ROOT/src"
"${ROOT}/.venv/bin/python" scripts/refresh.py "$@"
