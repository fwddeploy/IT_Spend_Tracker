#!/usr/bin/env bash
# One-command set-up for a fresh Ubuntu server (DigitalOcean droplet, 2 GB or more).
#
#   curl -fsSL https://raw.githubusercontent.com/fwddeploy/IT_Spend_Tracker/main/deploy/setup.sh | bash
#
# It installs Docker, fetches the code, makes the passwords, and starts the app with HTTPS.
set -euo pipefail

REPO="${REPO:-https://github.com/fwddeploy/IT_Spend_Tracker.git}"
DIR="${DIR:-/opt/it-tracker}"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Run this as root:  sudo bash setup.sh"
command -v apt-get >/dev/null || die "This script is for Ubuntu/Debian servers."

# ---------- what we need to know ----------
DOMAIN="${DOMAIN:-}"
EMAIL="${EMAIL:-}"
if [ -z "$DOMAIN" ]; then
  read -rp "Your domain name, already pointed at this server (e.g. tracker.fwddeploy.com): " DOMAIN
fi
[ -n "$DOMAIN" ] || die "A domain is required — HTTPS needs one."
if [ -z "$EMAIL" ]; then
  read -rp "Your email (for the HTTPS certificate notices): " EMAIL
fi

say "Installing Docker (this takes a minute)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl git ufw >/dev/null
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh >/dev/null
fi
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin missing — install it and run again."

say "Opening the firewall for web traffic"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 80/tcp   >/dev/null 2>&1 || true
ufw allow 443/tcp  >/dev/null 2>&1 || true
yes | ufw enable   >/dev/null 2>&1 || true

say "Getting the code into $DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$DIR"
fi
cd "$DIR"

say "Writing settings"
if [ -f .env ]; then
  echo "    .env already exists — keeping it (delete it if you want fresh passwords)."
else
  SECRET_KEY="$(openssl rand -base64 48 | tr -d '\n/+=' | cut -c1-48)"
  POSTGRES_PASSWORD="$(openssl rand -base64 24 | tr -d '\n/+=' | cut -c1-24)"
  cat > .env <<EOF
# Written by deploy/setup.sh on $(date -u +%Y-%m-%d). Keep this file private.
DOMAIN=$DOMAIN
ACME_EMAIL=$EMAIL

SECRET_KEY=$SECRET_KEY
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# 0 = start empty (correct for a real customer). 1 = load the sample factory.
SEED_SAMPLE=0

# Optional extra key for scripts (X-Access-Key header). Empty = not used.
APP_ACCESS_KEY=

# WhatsApp reminders (Meta Cloud API) — fill in when you have them
WA_PHONE_NUMBER_ID=
WA_TOKEN=
WA_TEMPLATE_NAME=

# Email reminders
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=
EOF
  chmod 600 .env
  echo "    new passwords written to $DIR/.env"
fi

say "Building and starting (first time takes 3-5 minutes)"
docker compose -f docker-compose.prod.yml up -d --build

say "Waiting for the app to answer"
for i in $(seq 1 60); do
  if docker compose -f docker-compose.prod.yml exec -T app python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" >/dev/null 2>&1; then
    OK=1; break
  fi
  sleep 5
done

echo
if [ "${OK:-0}" = "1" ]; then
  printf '\033[1;32m'
  cat <<EOF
====================================================================
  Done.  Open:  https://$DOMAIN
  The certificate can take a minute the first time.

  Make your login on the page -> Register.
  Settings are in $DIR/.env  (passwords are in there — keep it private)

  Useful commands, run inside $DIR :
    docker compose -f docker-compose.prod.yml logs -f app     see what it is doing
    docker compose -f docker-compose.prod.yml restart app     restart
    bash deploy/update.sh                                     get the latest code
    bash deploy/backup.sh                                     save a copy of the data
====================================================================
EOF
  printf '\033[0m'
else
  die "The app did not answer in time. Look at the logs:
  cd $DIR && docker compose -f docker-compose.prod.yml logs app"
fi
