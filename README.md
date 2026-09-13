# IT Tracker

One screen that shows a small factory every software / licence it pays for, what goes out this month, what is due next — built from files they already have (bank statement, Tally export), with nothing to install on their side.

```
messy payments in  →  one engine  →  one clean list + due dates + reminders
```

## Run it (Docker, recommended)

```bash
docker compose up --build
# open http://localhost:8000  — a sample factory is already loaded
# log in as  demo@ittracker.local / demo1234
```

## Run it (local dev)

```bash
# backend (SQLite by default; set DATABASE_URL for Postgres — see .env.example)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend (dev server proxies /api to :8000)
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # -> frontend/dist, served by the backend at http://localhost:8000
```

Tests:

```bash
cd backend
python -m pytest -q                 # engine cases + end-to-end API flows (SQLite temp files)
DATABASE_URL=postgresql+psycopg2://ittracker:ittracker@localhost:5432/ittracker python -m pytest -q   # same suite on Postgres (drops + recreates the schema)
```

## Login, roles, demo account

Every `/api` route needs a login (cookie session, 30 days) — except `/api/auth/*` and `/api/health`.

- **Demo**: on an empty database the app seeds a sample factory (`SEED_SAMPLE=1`, the default) owned by
  **demo@ittracker.local / demo1234** (also printed in the startup log). Set `SEED_SAMPLE=0` to start empty and
  register your own account at `POST /api/auth/register` (this creates your first company).
- **Roles** per company: `owner` (everything, incl. settings, delete, invite), `accountant` (upload, edit lines, answer
  questions, send reminders), `viewer` (read only). Owners invite people with `POST /api/auth/invite` — a new user gets a
  one-time password in the response (no email sending in this build).
- **Scripts**: if `APP_ACCESS_KEY` is set, requests carrying `X-Access-Key: <key>` are treated as an owner of every company.
- Set `SECRET_KEY` in production (it signs the cookie); `COOKIE_SECURE=1` behind HTTPS.

## Reminders (WhatsApp / email)

A scheduler inside the app runs every hour (`SCHEDULER=0` disables it). For each company with a channel switched on in
Settings (`owner_phone` + `whatsapp_enabled`, `owner_email`/`accountant_email` + `email_enabled`), it sends a reminder for every
line with the bell on when `next_due - today` equals the configured days-before (monthly 5 / quarterly 10 / yearly 30 by
default), and again every 7 days while a line is overdue. Each send is written to the reminder log (status `sent`, `failed`
or `skipped_not_configured`); `GET /api/companies/{id}/reminders` previews what will go out, `POST .../reminders/send-now`
sends one line immediately, `POST /api/internal/reminders/run` runs the whole loop by hand.

Environment (all optional — without them reminders are logged as `skipped_not_configured`, nothing breaks):

| Channel | Variables |
|---|---|
| WhatsApp (Meta Cloud API) | `WA_PHONE_NUMBER_ID`, `WA_TOKEN`, optional `WA_TEMPLATE_NAME` (approved template; empty = plain text message, POC), `WA_TEMPLATE_LANG=en`, `WA_API_VERSION=v20.0` |
| Email (SMTP) | `SMTP_HOST`, `SMTP_PORT` (587 STARTTLS / 465 SSL / 25 plain), `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` |

See `.env.example` for the full list.

## Export, FY view, share

- `GET /api/companies/{id}/export.xlsx` — Excel with Lines, Upcoming (12 months), Payments, Questions.
- `GET /api/companies/{id}/dashboard?fy=2026` — financial-year view (start month from Settings; past months show actual
  payments, future months the dues).
- `GET /api/companies/{id}/share-text` — a WhatsApp-ready summary for the owner.
- `GET /api/companies/{id}/events` — audit log of edits, uploads, answers and settings changes.

## Database

Postgres in production: the schema is managed by Alembic (`backend/alembic/`); the app runs `alembic upgrade head` on
start (a database created by v0.1 is adopted automatically). SQLite dev/tests use `create_all`. To add a column: edit
`models.py`, then `cd backend && DATABASE_URL=... alembic revision --autogenerate -m "what changed"`.

See `docs/REVIEW-v0.1.md` for what was reviewed, fixed and what is still open, and `docs/API-v2-additions.md` for the v2 API.

## What's inside

```
backend/
  app/
    main.py            FastAPI app; serves API + built frontend
    models.py          Company, User, Membership, Account, RawRow, Vendor, VendorAlias, Occurrence, Stream, Question,
                       ReminderLog, Event
    auth.py            bcrypt passwords, signed-cookie sessions, roles (owner / accountant / viewer)
    reminders.py       what is due for a nudge; WhatsApp (Meta Cloud API) + email (SMTP) senders; hourly run
    export.py          Excel export
    data/vendors.yaml  vendor dictionary: aliases, categories, default cycles, resellers, amount fingerprints,
                       narration hints, exclusions (bank fees, government, salary…), gateways
    parsers/           Excel/CSV/PDF statement + Tally register auto-detect; Tally XML
    engine/
      normalize.py     clean a bank narration into a payee name; detect payment mode
      vendors.py       who is this vendor? alias → gateway → reseller → narration → fingerprint → fuzzy → ask
      dedupe.py        same bill in bank + Tally + email → one payment; GST/TDS/forex/refund/split rules
      recurrence.py    does it repeat? cycle, expected amount, next due, confidence
      status.py        active / due soon / overdue / stopped / cancelled…; cash-out vs monthly-equivalent
      runner.py        DB orchestration; user edits are never overwritten; needs-attention questions
    sample.py          realistic sample company (also writes backend/samples/*.xlsx)
  tests/               62 engine/parser cases from the research + end-to-end API flows
frontend/              Vite + React + TS: Home, Lines, Upcoming, Attention, Upload
  alembic/             Postgres migrations
docs/API.md            API contract (v1) · docs/API-v2-additions.md (v2: auth, settings, reminders, export…)
```

## How it works (short)

1. **Upload** a bank statement (Excel/CSV/PDF) or a Tally purchase register (Excel/XML). Header row and columns are auto-detected. Re-uploading the same file adds nothing (rows are de-duplicated).
2. **Engine** runs automatically:
   - cleans every narration into a payee (`NEFT-N0001-SHREE INFOTECH-TSS` → `SHREE INFOTECH`),
   - drops non-IT lines (salary, raw material, GST, bank charges…),
   - recognises the vendor (alias list, reseller list, amount fingerprints like ₹5,310 = Tally TSS, narration words, learned answers),
   - merges the same bill seen in several sources, understanding GST, TDS, forex markup, refunds, split payments,
   - groups repeating payments into lines with cycle (monthly / quarterly / yearly / 3-yearly / prepaid), expected amount, next due and a confidence score,
   - raises a short question only when it really can't tell (unknown vendor, seen once, stopped paying).
3. **Screen**: "going out this month" and "monthly-equivalent" side by side, line items, next 12 months, needs-attention inbox. Every edit the accountant makes is kept across re-runs.

## Adding vendors / resellers

Edit `backend/data/vendors.yaml` — no code change. A payee the user classifies once is remembered for that company (`vendor_aliases` table); frequently confirmed strings can be promoted into the YAML.

## Next (not in this build)

Unique inbound email address + forwarding guide · WhatsApp inbound ("PAID" replies) · GSTR-2B pull via a GSP · Zoho Books / Microsoft 365 connectors · invite emails.
