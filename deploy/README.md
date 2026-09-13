# Putting IT Spend Tracker on a server

For a pilot you need it on the internet — a factory accountant cannot open `localhost` on your laptop.
One small server runs everything: the app, the database and HTTPS.

## What you need

| | |
|---|---|
| Server | DigitalOcean droplet, **Ubuntu**, **2 GB RAM** (about $12/month). 1 GB is too small — building the frontend needs memory. |
| Region | **Bangalore**. The data is Indian bank statements; keep it in India, and it is faster for customers. |
| Domain | any domain, e.g. `tracker.fwddeploy.com`. Add an **A record** pointing to the droplet's IP, and wait a few minutes. |

New DigitalOcean accounts get free credit for the first 60 days, which covers a whole pilot.

## Set it up (one command)

SSH into the droplet and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/fwddeploy/IT_Spend_Tracker/main/deploy/setup.sh | sudo bash
```

It asks for your domain and email, then does the rest: installs Docker, opens the firewall,
fetches the code, generates the passwords, and starts everything with automatic HTTPS.

First run takes 3–5 minutes. When it finishes, open `https://your-domain` and register your login.

If the repository is private, clone it first and run the script from inside:

```bash
git clone https://github.com/fwddeploy/IT_Spend_Tracker.git /opt/it-tracker
cd /opt/it-tracker && sudo bash deploy/setup.sh
```

## Day-to-day

Everything runs from `/opt/it-tracker`:

```bash
cd /opt/it-tracker

bash deploy/update.sh                                    # get the latest code and restart
bash deploy/backup.sh                                    # save a copy of the database
docker compose -f docker-compose.prod.yml logs -f app    # watch what it is doing
docker compose -f docker-compose.prod.yml restart app    # restart
docker compose -f docker-compose.prod.yml ps             # what is running
```

Nightly backups — run `crontab -e` and add:

```
0 2 * * * bash /opt/it-tracker/deploy/backup.sh >> /var/log/it-tracker-backup.log 2>&1
```

Copies go to `/opt/it-tracker-backups`, last 30 days kept. Download one to your PC with
`scp root@your-server:/opt/it-tracker-backups/*.sql.gz .`

## Settings

All of them live in `/opt/it-tracker/.env`, written by the setup script. Edit it, then
`docker compose -f docker-compose.prod.yml up -d` to apply.

| | |
|---|---|
| `SEED_SAMPLE` | `0` on a real server, so the demo factory is not created. `1` if you want it for a demo. |
| `SECRET_KEY`, `POSTGRES_PASSWORD` | generated for you. Changing `SECRET_KEY` logs everyone out. |
| `WA_*`, `SMTP_*` | fill in to make reminders actually send. Until then they are logged as "not set up". |

## Before the first real customer

- `SEED_SAMPLE=0` (the setup script already does this)
- remove the demo login if it exists: log in as it and delete the sample company, or start on a fresh database
- take a backup before every update
- keep `.env` private — it holds the passwords

## What is running

```
internet ──▶ Caddy (80/443, gets the HTTPS certificate itself)
                └──▶ app  (FastAPI + the built frontend, port 8000, not exposed publicly)
                       └──▶ db  (Postgres, data kept in a Docker volume)
```

## If something goes wrong

| Problem | What to do |
|---|---|
| Site does not open | Check the domain's A record points at the droplet IP: `dig +short your-domain`. Certificates need port 80 open. |
| "502" or blank page | `docker compose -f docker-compose.prod.yml logs app` |
| Build runs out of memory | Use a 2 GB droplet, or add swap: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile` |
| Need to start over | `docker compose -f docker-compose.prod.yml down -v` wipes the data too — take a backup first. |
