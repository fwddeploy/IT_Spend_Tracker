#!/usr/bin/env bash
# Pull the latest code and restart. Run inside the project folder on the server.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "==> pulling"
git pull --ff-only
echo "==> rebuilding"
docker compose -f docker-compose.prod.yml up -d --build
echo "==> done. Logs:  docker compose -f docker-compose.prod.yml logs -f app"
