#!/usr/bin/env bash
# Save a copy of the database to /opt/it-tracker-backups, keeping the last 30 days.
# Run it nightly:   0 2 * * *  bash /opt/it-tracker/deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${OUT:-/opt/it-tracker-backups}"
mkdir -p "$OUT"
FILE="$OUT/it-tracker-$(date -u +%Y%m%d-%H%M).sql.gz"
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U ittracker ittracker | gzip > "$FILE"
find "$OUT" -name 'it-tracker-*.sql.gz' -mtime +30 -delete
echo "saved $FILE"
