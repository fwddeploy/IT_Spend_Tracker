# Architecture

This document explains how IT Spend Tracker works, end to end, in enough detail that you can change any part of it without reading every file first. It is written for a developer who has never seen the code.

## 1. The one idea

```
┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐    ┌──────────────────┐
│  FILES       │    │  RAW ROWS    │    │  ENGINE                      │    │  SCREENS         │
│  bank Excel  │───▶│  one row per │───▶│  1 who is the vendor?        │───▶│  Home, Licences, │
│  Tally Excel │    │  statement   │    │  2 same bill seen twice?     │    │  Upcoming,       │
│  Tally XML   │    │  line        │    │  3 does it repeat? when next?│    │  Attention,      │
│  PDF / CSV   │    │              │    │  4 status + totals           │    │  Settings        │
└──────────────┘    └──────────────┘    └──────────────┬───────────────┘    └────────┬─────────┘
                                                        │ questions it can't answer   │ answers / edits
                                                        └────────────────────────────▶│ (learned, kept)
                                                                                      ▼
                                                                          reminders → WhatsApp / email
```

Adding a new source of data (an email inbox, the GST portal, Zoho Books) means adding one more way to produce raw rows. The engine and the screens do not change.

## 2. Components

| Part | Where | Stack |
|---|---|---|
| API + engine + reminder job | `backend/` | Python 3.11, FastAPI, SQLAlchemy 2, pandas, rapidfuzz, APScheduler |
| Database | Postgres (prod) / SQLite file (dev, tests) | Alembic migrations on Postgres; `create_all` on SQLite |
| Web app | `frontend/` | Vite, React 18, TypeScript, react-router; built into `frontend/dist` and served by the backend |
| Container | `backend/Dockerfile`, `docker-compose.yml` | one app container (non-root, 2 uvicorn workers, health check) + Postgres |

One process runs everything: API, static frontend, and the hourly reminder scheduler.

## 3. Data model (`backend/app/models.py`)

```
User ──< Membership >── Company ──< Account (bank / card / personal / tally)
                           │  ──< ImportBatch (one per uploaded file)
                           │  ──< RawRow      (one per line in a file)
                           │  ──< Occurrence  (one real payment; duplicates merged)
                           │  ──< Stream      (one line on the dashboard: a licence / subscription)
                           │  ──< Question    (needs-attention inbox)
                           │  ──< VendorAlias (answers the user gave; company-scoped)
                           │  ──< ReminderLog, Event (audit)
Vendor (global dictionary, seeded from data/vendors.yaml) ──< VendorAlias
```

- **RawRow** — the common shape every parser produces: `date, amount, direction, raw_description, payee_clean, payment_mode, invoice_no, period_from/to, taxable, gst, ledger, is_personal, dedupe_key`. `dedupe_key` (hash of source+date+amount+description, with a counter for identical lines in the same file) means re-uploading a file adds nothing.
- **Occurrence** — one payment after merging sources. Carries `amount_paid` (bank), `amount_gross` (invoice incl. TDS), `taxable, gst, tds, fees` (forex markup), `sources` (`["bank","tally"]`), `unpaid` (booked in Tally, no bank line yet).
- **Stream** — the dashboard line. `stream_key` is stable across engine runs (vendor + product + coarse amount bucket). `user_fields` holds everything the user set; the engine never overwrites those keys. `extra` holds engine extras (RCM amount, seat count, supplier history, change note).
- **Question** — `kind` ∈ `vendor | cycle | stopped | bundle`, `options` the user can pick, keyed so re-runs don't duplicate it.

## 4. Parsers (`backend/app/parsers/`)

`tabular.py` reads Excel / CSV / PDF. It searches the first 40 rows for the header (bank statements start with account details), matches columns by a synonym list (`Withdrawal Amt`, `Debit`, `DR`, `Amount` + `Dr/Cr`…; punctuation-insensitive), parses Indian date shapes day-first, handles "1,45,000.00", "Rs.", "(500)", "500-" and "1,769.00 Cr". For Tally exports it prefers the party column (`Particulars`) as the payee and keeps the narration separately. `detect_bank()` finds the bank name in the header. `tally_xml.py` reads Tally's XML export (vouchers, ledgers, GST ledgers, cheque numbers). Password-protected PDFs take `pdf_password`.

Output of every parser: a list of dicts in the RawRow shape above, plus `detected_format`, rows skipped, and bank.

## 5. The engine (`backend/app/engine/`)

Run order (in `runner.run_engine`): normalize → resolve vendors → build occurrences → build streams → status → questions. All of it is deterministic rules; no ML. Tests for every rule are in `backend/tests/test_engine*.py`, numbered after the cases in `docs/research/3-engine-logic-and-test-cases.md`.

### 5.1 `normalize.py` — narration → payee
- Strips bank prefixes (`POS`, `VIN/`, `NEFT-`, `IMPS/`, `ACH D-`, `IB BILLPAY DR-`, `TO TRANSFER-`…), transaction ids, dates, masked card fragments, city and legal suffixes (`PVT LTD`, `DUBLIN`, `REDMOND WA`).
- NEFT/RTGS/IMPS narrations are split into segments; the first segment that is a name (not a UTR, not a bank code, not a mode word) is the payee: `NEFT-N0001-SHREE INFOTECH-TSS RENEWAL` → `SHREE INFOTECH`.
- UPI: the VPA carries the merchant (`tallysolutions.rzp@hdfcbank` → `TALLYSOLUTIONS`); phone-number handles are ignored.
- Cheques keep their number (`CHQ 000412`) so they can be matched to Tally.
- `detect_mode()` → `card | upi | neft | rtgs | imps | cheque | nach | si | netbanking | cash`. Card / SI / NACH mean auto-renew.

### 5.2 `vendors.py` — who is this vendor?
Everything comes from `data/vendors.yaml`. Order of attempts, cheapest first:
1. **Learned aliases** for this company (answers the user gave) — anchored regex, win outright.
2. **Global alias dictionary** — ~90 vendors, regexes with word boundaries (`MSFT\s?\*`, `GOOGLE\s?\*\s?WORKSPACE`, `DASSAULT`, `TALLY SOLUTIONS`…). Narration words may refine the product.
3. **Payment gateway** wrappers (`RAZORPAY`, `PAYU*`, `PAYPAL *`, `STRIPE*`) are stripped and the remainder retried.
4. **Reseller directory** (~70 Indian partners with what they sell). A reseller with a narration hint or a list-price fingerprint resolves to the product; without either it becomes a **bundle** (asks the user).
5. **Narration hints** (`TSS` → Tally, `SOLIDWORKS`, `SEQRITE`, `IT AMC`, `SAP B1`…).
6. **Amount fingerprints** — exact list prices (₹5,310 = TSS Silver + GST) and per-seat prices (`infer_quantity`: 10 users × ₹145).
7. **Fuzzy** match against multi-word aliases only.
8. Unknown → flagged `looks_it` if the name has IT-ish words (INFOTECH, TECHNOLOGIES…), which decides whether a question is worth asking.

Also: exclusion patterns (bank charges, government, salary, electricity, fuel…, all word-bounded), forex-markup detection, term text (`3 years`, `annual`, `FY 26-27` → months), hardware words.

### 5.3 `dedupe.py` — raw rows → occurrences
- Drops excluded rows and ≤ ₹5 authorisation charges; credits are never excluded (they may be refunds).
- Refund within 30 days cancels the nearest matching debit; duplicate debit + reversal keeps one.
- Forex markup lines (`MARKUP`, `DCC`) within 3 days and ≤ 6 % of a foreign debit are folded in as `fees`.
- Bank/card rows become occurrences first; bill rows (Tally / email / GST) attach to them by: same invoice number → same cheque number (last 6 digits) → same vendor + amount relation + date window (bank↔Tally 60 days, bank↔email 15).
- Amount relation between a bank debit and an invoice: `total`, `taxable×1.18`, `total − taxable×TDS%` (1 / 2 / 10 / 20 %), `taxable` only (flagged), with a strict 0.3 % tolerance first and a loose ₹50 / 2 % tolerance for rounded UPI payments.
- Two payments within 45 days that sum to one invoice merge (`paid_in_2_parts`).
- A Tally bill with no bank line in 60 days becomes an `unpaid` occurrence ("booked, not paid") and counts as due now.
- Hardware-only bills route to the `hardware` vendor (one-time); mixed bills keep the software vendor and flag `mixed_hardware_bill`.

### 5.4 `recurrence.py` — occurrences → streams
- Group by vendor (or cleaned payee) and currency; split by known product; cluster amounts into bands (±12 %), then merge bands that are a step change (seat change / price hike, ratio 0.5–2.5×) into one stream with an `amount_history` and a `change_note`.
- A lone payment ≥ 3× the repeating amount, occurring first, is a **one-time licence**; the repeating part is the AMC / subscription (narration "LICENCE/PERPETUAL" lowers the threshold to 2×).
- Cycle from the **median gap** between payments: monthly 27–34 days, quarterly 84–98, half-yearly 170–195, yearly 340–395, 2-yearly 700–760, 3-yearly 1060–1130; per-gap tolerance ±5 / 10 / 15 / 30 / 40 / 45 days; 2× and 3× gaps count as missed cycles. N× amounts anywhere in the history are catch-up payments, not price changes.
- Single payment: invoice period or term text decides the cycle; else the vendor's default; else "irregular".
- Variable vendors (AWS, telecom): amounts may swing ±60 %, cycle from dates only, expected = median of last 3. Prepaid vendors (SMS credits): no due date, expected = 6-month average run-rate.
- Expected amount = **last** amount (after a price change the last one predicts), average kept for display; USD vendors grouped on `fx_amount` when present.
- Next due: invoice `period_to + 1` → else last paid + cycle, snapped to the usual day (median day-of-month, or day-of-year for yearly; clamped to month length); paid early keeps the previous expected due; catch-ups push it N cycles.
- Confidence 0–100: +30 for ≥3 payments (+20 for 2), +25 × share of gaps that fit, +15 stable amounts, +15 if the cycle matches the vendor's default, +10 invoice/period text, +5 auto-pay, +10 for narration/fingerprint/user resolution, −10 gateway guess. A known vendor with an invoice stating the term is accepted from one payment.
- Post-passes: supplier switch (same vendor, old payee stops within a cycle of the new one starting, ±25 % per month) merges into one stream with `supplier_history`; unknown payees that are neither IT-ish nor regular are dropped (raw-material suppliers never appear).
- Flags produced: `one_time_licence, cycle_from_invoice, cycle_from_vendor_default, price_changed, tds_deducted, rcm_gst_payable, paid_from_personal, not_in_company_books, booked_not_paid, forex_markup, paid_in_2_parts, catch_up_N_cycles, topup_every_Nd, supplier_changed, bundle_unknown_product, mixed_hardware_bill, cheque_matched, paid_early, intro_price_renewal_may_be_higher`. The API turns each into plain English (`flags_human`).

### 5.5 `status.py` — status and the two totals
- `needs_confirm` when confidence < 75 and the user hasn't touched the line; `one_time`; prepaid → `active`.
- `due_soon` within 5 / 10 / 20 / 30 / 45 days (by cycle); `overdue` (manual pay) or `charge_missed` (auto pay) after a grace of 7 / 15 / 20 / 30 / 40 days; `stopped` after one full extra cycle (AMC lines → `amc_lapsed`); `cancelled` when a refund or cancellation is seen or the user says so; `dismissed` when hidden.
- **Going out this month** = payments already made this month (live lines only) + everything still due this month, overdue items counted as due now + run-rate estimate for pay-as-you-go lines. Returned with the breakdown `{paid, still_due, estimate}`.
- **Monthly-equivalent** = Σ expected ÷ months-in-cycle (yearly ÷ 12…). Annualised = ×12. Also by category, auto-renew vs manual, and a 12-month (or FY Apr–Mar) calendar.

### 5.6 `runner.py` — persistence and questions
- Idempotent: every run rebuilds occurrences and streams; existing streams are matched by `stream_key`; keys in `user_fields` are never overwritten; a user-typed `next_due` is released once a newer real payment arrives; manual streams and user-modified streams are never deleted.
- Runs under a per-company lock (thread lock + Postgres advisory lock).
- Questions: `vendor` (unknown payee worth ≥ ₹5,000 a year or IT-ish), `cycle` (known vendor seen once, no term text), `stopped` (no payment for a cycle+), `bundle` (reseller bill with no product). Answers create a company-scoped `VendorAlias` (anchored) and re-run the engine; `split` turns a bundle into several manual lines. Answered questions are kept for the audit trail.
- Vendor and alias tables are seeded from `vendors.yaml` at startup (`seed_vendors`).

## 6. API (`backend/app/api/`)

`docs/API.md` lists every route. Shape: `/api/companies/{id}/…` for everything company-scoped; `/api/auth/*`; `/api/vendors`; `/api/health`. Responses are Pydantic models in `schemas.py`; `stream_out()` in `routes.py` is the single place a Stream becomes JSON (adds monthly-equivalent, RCM amount, seat count, FY, plain-English flags).

## 7. Auth (`backend/app/auth.py`)

Email + password (bcrypt), signed cookie session `it_session` (itsdangerous, 30 days, `SECRET_KEY`). `Membership.role` ∈ `owner > accountant > viewer`; `require_company(role)` is a FastAPI dependency on every company route and returns the Company or 403. `X-Access-Key` (env `APP_ACCESS_KEY`) is an alternative principal for scripts. `/api/companies` only lists the caller's companies.

## 8. Reminders (`backend/app/reminders.py`)

- Candidates: live streams with `reminder_on` and a `next_due`.
- Send when `next_due − today` equals the company's `days_before` for that cycle bucket (defaults monthly 5, quarterly 10, yearly 30) or when overdue and not reminded in the last 7 days.
- Channels: WhatsApp (Meta Cloud API — template if `WA_TEMPLATE_NAME` set, else plain text) to `owner_phone`; email (SMTP) to owner and accountant. Unconfigured channel → log row with status `skipped_not_configured`.
- `ReminderLog` de-duplicates on stream + due + channel + recipient. Preview, send-now and log are exposed in Settings.
- `APScheduler` runs `run_reminders` hourly inside the app (skip with `SCHEDULER=0`); a Postgres advisory lock stops two workers sending twice.

## 9. Frontend (`frontend/src/`)

`lib/api.ts` — typed functions for every endpoint (401 → login redirect); `lib/auth.tsx`, `lib/company.tsx` — session and current company (localStorage, try/catch); `pages/` — Home, Lines (licences), Upcoming, Attention, Upload (with onboarding), Settings, Login, Register; `components/StreamDrawer.tsx` — the line editor (Mark paid, Pay now, edit, details, history); `lib/format.ts` — Indian rupee grouping, dates, plain-English labels for statuses, cycles, categories, flags. No UI framework; one `styles.css` with CSS variables; phone layouts below 640 px.

## 10. Security notes

Every API call needs a login; uploads are capped at 25 MB with magic-byte checks; internal errors are logged, not shown; dates use Asia/Kolkata; bank narrations are personal data — run Postgres on an encrypted disk, put TLS in front, set `SECRET_KEY`, and back up nightly (`pg_dump`). Money is stored as float (adequate for INR at this scale; switch to `Numeric` if you ever do accounting-grade sums).
