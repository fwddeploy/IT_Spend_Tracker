# IT Tracker

One screen that shows a small factory every software / licence it pays for, what goes out this month, what is due next — built from files they already have (bank statement, Tally export), with nothing to install on their side.

```
messy payments in  →  one engine  →  one clean list + due dates + reminders
```

## Run it (Docker, recommended)

```bash
docker compose up --build
# open http://localhost:8000  — a sample factory is already loaded
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
python -m pytest -q                 # engine cases + end-to-end API flow
DATABASE_URL=postgresql+psycopg2://ittracker:ittracker@localhost:5432/ittracker python -m pytest -q tests/test_api.py
```

Optional: set `APP_ACCESS_KEY=somesecret` (in `.env` / compose) and the page will ask for that key once before showing any data. Set `SEED_SAMPLE=0` to start empty. See `docs/REVIEW-v0.1.md` for what was reviewed, fixed and what is still open.

## What's inside

```
backend/
  app/
    main.py            FastAPI app; serves API + built frontend
    models.py          Company, Account, RawRow, Vendor, VendorAlias, Occurrence, Stream, Question
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
docs/API.md            API contract
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

Unique inbound email address + forwarding guide · WhatsApp intake and reminders · GSTR-2B pull via a GSP · Zoho Books / Microsoft 365 connectors · reminder scheduler · multi-user auth.
