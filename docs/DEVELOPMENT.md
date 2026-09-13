# Development guide

## Set-up

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000              # SQLite file backend/it_tracker.db, sample company seeded

# frontend (separate terminal)
cd frontend
npm install
npm run dev                                            # http://localhost:5173, proxies /api to :8000
```

To use Postgres locally: `export DATABASE_URL=postgresql+psycopg2://ittracker:ittracker@localhost:5432/ittracker` (create the role/db first). Migrations run automatically at startup on Postgres.

Demo login: `demo@ittracker.local / demo1234`. `SEED_SAMPLE=0` starts empty.

## Tests

```bash
cd backend
python -m pytest -q                       # everything (~10 s)
python -m pytest -q tests/test_engine.py  # engine rules only
DATABASE_URL=postgresql+psycopg2://... python -m pytest -q   # same suite on Postgres
```

Test files:
- `tests/test_engine.py`, `tests/test_engine_gaps.py` — one test per rule from `docs/research/3-engine-logic-and-test-cases.md` (case numbers in the test names).
- `tests/test_parsers.py` — bank formats (HDFC, ICICI, SBI, Axis, Kotak, card statements), Tally Day Book / register / XML, PDF, `.xls`, edge cases.
- `tests/test_api.py`, `tests/test_v2_api.py` — end-to-end flows through the HTTP API (upload → engine → dashboard → answer → edit → mark paid; auth, settings, reminders, export, delete).

Write a test before changing a rule. The engine is rules; a change that fixes one statement often breaks another, and the suite is the only thing that tells you.

## How do I…

### …teach it a new vendor?
Edit `backend/app/data/vendors.yaml` → `vendors:`. One entry:
```yaml
- {key: keka, name: Keka HR, category: hr, default_cycle: monthly, aliases: ['\bKEKA\b'], pay_url: 'https://app.keka.com'}
```
Aliases are regexes matched (case-insensitive) against the cleaned payee. Use `\b` word boundaries; a bare word like `KEKA` would also match "KEKASHI SWEETS". Optional flags: `variable: true` (usage-based amounts), `prepaid: true` (credits/top-ups), `entity_type: foreign_no_gst` (reverse-charge GST), `currency: USD`, `intro_pricing: true`. Restart the app (vendors are seeded at startup) and add a line to `test_vendor_aliases_do_not_over_match` if the alias is short.

### …add a reseller?
`vendors.yaml` → `resellers:` — `{name: SHREE INFOTECH, sells: [tally, quickheal]}`. The name is matched as a substring of the cleaned payee. `sells` becomes the option list when the engine asks "which product is this?".

### …add a known list price?
`vendors.yaml` → `fingerprints:` (exact amounts, e.g. TSS Silver ₹5,310) or `seat_prices:` (per-seat units used to infer "10 users × ₹145").

### …hide a kind of payment for everyone?
`vendors.yaml` → `exclude_patterns:`. Always word-bounded. Test that it doesn't hide a real vendor (`tests/test_engine.py::test_case44_45_bank_fees_and_government_excluded`).

### …support a bank format the parser doesn't read?
Add the column names to `SYN` in `backend/app/parsers/tabular.py` (date / desc / debit / credit / amount / drcr / ref). Build a tiny fixture in `tests/test_parsers.py` in the same style as the existing ones. If the statement has a preamble that breaks CSV parsing, see `_read_csv`. PDFs go through `pdfplumber` tables; scanned PDFs are not supported (ask for the Excel).

### …change how a rule works?
Find the rule number in `docs/research/3-engine-logic-and-test-cases.md`, the matching test, then the code: narration cleaning → `engine/normalize.py`; vendor recognition → `engine/vendors.py`; merging bills/payments → `engine/dedupe.py`; cycles / due dates / confidence → `engine/recurrence.py`; statuses and totals → `engine/status.py` (+ `dashboard()` in `api/routes.py`); questions and persistence → `engine/runner.py`.

### …add an API route?
`backend/app/api/routes.py` (handler) + `schemas.py` (Pydantic in/out). Use `Depends(require_company("accountant"))` (or `"viewer"` / `"owner"`) to get the Company and enforce the role. Write an `_event(...)` line for anything that changes data. Add the typed client function in `frontend/src/lib/api.ts` and document it in `docs/API.md`. Add a test in `tests/test_v2_api.py`.

### …add a database column?
Edit `models.py`, then on Postgres: `cd backend && alembic revision --autogenerate -m "add x" && alembic upgrade head`. SQLite dev databases are recreated by deleting `it_tracker.db`.

### …add a screen?
`frontend/src/pages/`, register the route in `App.tsx`, add the nav link in `components/Layout.tsx`. Use `useCompany()` for the current company and role (`canEdit`, `isOwner`), `useFetch` for loading/error states, and `format.ts` helpers so rupees and dates look Indian everywhere.

### …add a new data source (email, GST portal, Zoho)?
Produce rows in the RawRow shape (see `runner.ingest_rows`) with `source` = `email` / `gst` / `tally`. Bill sources attach to bank payments in `dedupe.py` using invoice number, cheque number, or vendor + amount relation within `WINDOW`. Nothing else changes.

## Conventions

- Plain-English error messages for anything a user can see (`HTTPException(400, "…")`); internal errors are logged and replaced with a generic message.
- Money: floats, rounded to 2 dp on output; rupee formatting is Indian grouping (₹2,45,568) in both the UI and the share text.
- Dates: `date` objects; "today" is India time (`runner.today_ist()`), never `date.today()` in engine code — tests pass a fixed `today`.
- User edits are stored in `Stream.user_fields` and are sacred: the engine writes around them.
- Keep it simple: no new frameworks, no queues, no ML. A rule with a test beats a clever heuristic.

## Deploy checklist

1. `DATABASE_URL` → Postgres on an encrypted disk; `SECRET_KEY` → long random string; `SEED_SAMPLE=0`.
2. TLS in front (Caddy / nginx); `CORS_ORIGINS` → your domain (same-origin needs nothing).
3. WhatsApp: create a Meta Business app, get `WA_PHONE_NUMBER_ID` + permanent `WA_TOKEN`, approve a utility template, set `WA_TEMPLATE_NAME`. Email: any SMTP.
4. `docker compose up -d --build`; check `GET /api/health`.
5. Nightly `pg_dump` to object storage, 30-day retention.
6. First real customer: upload their last 24 months, sit with the accountant for the questions, and add every reseller they name to `vendors.yaml`.
