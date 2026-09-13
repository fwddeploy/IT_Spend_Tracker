# CLAUDE.md — context for AI coding assistants

Read this first. It tells you what this project is, how it is built, how to run and test it, and the rules to follow when changing it. Detailed docs are linked at the end; read them when a task touches that area.

## What this is

IT Spend Tracker: a web app for small Indian factories (MSMEs) that shows every software licence / subscription they pay for, "going out this month", "monthly-equivalent", next due dates, and sends WhatsApp/email reminders before renewals. Data comes from files the customer already has (bank statement Excel/CSV/PDF, Tally purchase register Excel/XML) — nothing is installed at the customer. An engine of plain rules recognises vendors (incl. resellers and payment gateways), merges the same bill seen in several sources (GST / TDS / forex aware), detects what repeats, and asks the user a short question only when it cannot tell.

Users: the factory owner (glances on a phone), the accountant (uploads, answers questions, marks paid), sometimes their outside CA (many companies). Everything on screen must be plain English, not engineering words.

## Stack and layout

- `backend/` — Python 3.11, FastAPI, SQLAlchemy 2, pandas, rapidfuzz, APScheduler. Postgres in prod (Alembic), SQLite in dev/tests.
  - `app/engine/` — `normalize.py` (narration → payee), `vendors.py` (who is the vendor; reads `app/data/vendors.yaml`), `dedupe.py` (rows → payments), `recurrence.py` (payments → lines with cycle / next due / confidence), `status.py` (statuses, totals), `runner.py` (DB orchestration, questions, user-field protection).
  - `app/parsers/` — `tabular.py` (Excel/CSV/PDF, column auto-detect, bank detect), `tally_xml.py`.
  - `app/api/` — `routes.py`, `schemas.py`; `app/auth.py` (login, roles); `app/reminders.py` (WhatsApp/email job); `app/export.py`; `app/sample.py` (demo company).
  - `tests/` — 107 tests: engine rules (`test_engine*.py`), parsers, HTTP flows.
- `frontend/` — Vite + React 18 + TypeScript, no UI framework. `src/lib/api.ts` (typed client), `src/pages/*`, `src/components/StreamDrawer.tsx`, `src/lib/format.ts` (Indian rupees, dates, plain labels).
- `docs/` — ARCHITECTURE.md (read for any engine work), DEVELOPMENT.md (how-tos), API.md, ROADMAP.md, research/ (the design basis), history/.

## Run / test

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000   # SQLite, sample seeded
cd frontend && npm install && npm run dev        # dev UI on :5173 → proxies /api to :8000
cd frontend && npm run build                     # backend serves frontend/dist on :8000
cd backend && python -m pytest -q                # must stay green; run before and after any change
docker compose up --build                        # app + Postgres on :8000
```
Demo login: `demo@ittracker.local / demo1234`. Env vars are documented in `.env.example` and README.

## Deploying

`deploy/setup.sh` sets up a fresh Ubuntu server in one command (Docker, firewall, code, generated
passwords, `docker-compose.prod.yml` = app + Postgres + Caddy for automatic HTTPS).
`deploy/update.sh` pulls and restarts; `deploy/backup.sh` dumps the database. See `deploy/README.md`.
Production differences from dev: `SEED_SAMPLE=0`, `COOKIE_SECURE=1`, the app port is not exposed
(Caddy proxies to it), and passwords come from the server's `.env`.

## Rules when changing things

1. **Tests first.** Every engine rule has a numbered test (`docs/research/3-engine-logic-and-test-cases.md` → `tests/test_engine*.py`). Add or update the test, then the code. Run the full suite; on Postgres too if you touched models (`DATABASE_URL=postgresql+psycopg2://ittracker:ittracker@localhost:5432/ittracker`).
2. **Vendors live in YAML, not code.** New vendor / reseller / list price / exclusion → `backend/app/data/vendors.yaml`. Regexes must use `\b` word boundaries (short aliases over-match: `KEKA` would hit "KEKASHI SWEETS").
3. **User edits are sacred.** Anything the user set is in `Stream.user_fields`; the engine must never overwrite those keys on a re-run. A user-typed `next_due` is released only when a newer real payment arrives (`next_due_basis`).
4. **Engine is deterministic rules.** No ML, no network calls inside the engine. "Today" comes from the caller (`today` param; `runner.today_ist()` = Asia/Kolkata) — never `date.today()` in engine code.
5. **Plain English on screen.** Errors users can see are full sentences saying what to do (`"Could not find the header row… Export the statement as Excel from net banking."`). Never leak tracebacks. Use "licences", "payments", "re-check" — not "streams", "occurrences", "engine". Flags are mapped to text in `routes.py: FLAG_TEXT`.
6. **Indian formats.** Rupees with Indian grouping (₹2,45,568 — `format.ts rupees()`, `routes.py inr()`), dates day-first, FY April–March, GST 18 %, TDS 1/2/10/20 %.
7. **Every company route** takes `Depends(require_company("viewer"|"accountant"|"owner"))` and writes an `_event(...)` when it changes data.
8. **Schema changes** → edit `models.py` + `alembic revision --autogenerate` (Postgres). SQLite dev DB: delete `backend/it_tracker.db`.
9. **Keep it simple.** No new frameworks, queues, or services. One process runs API, static frontend and the reminder scheduler. If a change needs more than that, discuss first.
10. **Don't commit** `*.db`, `frontend/dist`, `node_modules`, `.env`, or the generated `backend/samples/*.xlsx` (see `.gitignore`).

## Where things are decided

- Which vendor a payment belongs to → `vendors.py: Catalog.resolve` (order: learned alias → global alias → gateway → reseller → narration → fingerprint → fuzzy → unknown).
- Whether two rows are the same bill → `dedupe.py: build_occurrences` (`_amount_relation` for GST/TDS maths, `WINDOW` for date windows).
- Cycle / next due / confidence → `recurrence.py: _stream_from_band`; cycle tolerances in `CYCLES`.
- Status names and windows → `status.py`; "going out this month" maths → `routes.py: dashboard()`.
- When a question is asked → `runner.py: _make_questions`; what an answer does → `runner.py: answer_question`.
- When a reminder is sent → `reminders.py: compute_due_reminders`.

## Useful facts

- Sample data (`app/sample.py`) is generated relative to today and covers: reseller-billed SolidWorks with TDS, Tally licence + TSS renewals, M365 seat change, AWS variable, Adobe USD with forex markup, Seqrite 3-year, GoDaddy yearly, Airtel NACH, MSG91 prepaid, IT AMC quarterly, Zoom stopped with a refund, an unknown yearly payee, a reseller bundle, a booked-not-paid SAP AMC, plus noise (salary, raw material, GST, bank charges).
- Confidence ≥ 75 auto-accepts a line; 45–74 shows "Is this a subscription?"; below that it stays hidden unless worth asking about.
- The `X-Access-Key` header (env `APP_ACCESS_KEY`) is an alternative to login for scripts/tests.

## Docs to read by task

| Task | Read |
|---|---|
| Any engine or parser change | `docs/ARCHITECTURE.md` §4–5, the matching cases in `docs/research/3-engine-logic-and-test-cases.md` |
| New route / screen / column | `docs/DEVELOPMENT.md` "How do I…", `docs/API.md` |
| New data source (email, GST, Zoho) | `docs/ROADMAP.md`, `docs/research/2-integration-options.md`, `runner.ingest_rows` |
| Why the product is shaped this way | `docs/research/1-market-research.md`, `docs/history/BUILD-PLAN.md` |
