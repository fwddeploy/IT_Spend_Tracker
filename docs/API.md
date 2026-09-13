# IT Tracker — API contract (v1)

Base URL: `/api`. JSON everywhere. Dates are `YYYY-MM-DD`. Money is INR float (2 dp). All company-scoped routes take `company_id` (int).

## Companies
- `GET /companies` → `[Company]`
- `POST /companies` `{name, gstin?, fy_start_month?=4}` → `Company`
- `GET /companies/{id}` → `Company`

`Company = {id, name, gstin, fy_start_month, created_at}`

## Upload & engine
- `POST /companies/{id}/upload` multipart: `file`, `source_kind` (`bank|card|tally|generic`), `account_label` (e.g. "HDFC Current", "MD personal card"), `is_personal` (bool, default false)
  → `{batch: ImportBatch, engine: EngineSummary}` (engine runs automatically after import)
- `POST /companies/{id}/run` → `EngineSummary`
- `GET /companies/{id}/imports` → `[ImportBatch]`
- `GET /companies/{id}/accounts` → `[Account]`

`ImportBatch = {id, filename, source_kind, account_label, rows_imported, rows_skipped, detected_format, created_at, error?}`
`EngineSummary = {occurrences, streams, questions_open, auto_accepted, needs_confirm, unclassified, ran_at}`
`Account = {id, label, kind (bank|card|personal|tally), bank_name?}`

## Dashboard
- `GET /companies/{id}/dashboard?month=YYYY-MM` (default current month) →
```
{
  month, cash_out_month, monthly_equivalent, annualised,
  active_count, due_soon_count, overdue_count, needs_confirm_count,
  by_category: [{category, monthly_equivalent, count}],
  next_dues: [StreamOut ×5],
  calendar: [{month:"2026-10", cash_out, items:[{stream_id, vendor_name, product, amount, due}]} ×12],
  committed_vs_manual: {auto_renew: x, manual: y},
  sync_health: [{account_label, source_kind, last_data_date, last_import_at, stale: bool}]
}
```

## Streams (one line per licence/subscription)
- `GET /companies/{id}/streams?status=&category=&q=` → `[StreamOut]`
- `GET /companies/{id}/streams/{sid}` → `StreamDetail` (= StreamOut + `occurrences: [Occurrence]`, `amount_history`)
- `POST /companies/{id}/streams` (manual add) `{vendor_name, product, category, cycle, expected_amount, next_due?, last_paid_date?, auto_renew?, paid_from?, owner_name?, pay_url?, notes?}` → `StreamOut`
- `PATCH /companies/{id}/streams/{sid}` any of `{vendor_name, product, category, cycle, expected_amount, next_due, status, auto_renew, paid_from, owner_name, pay_url, reminder_on, notes}` → `StreamOut` (sets `is_user_modified=true`; engine never overrides user fields)
- `POST /companies/{id}/streams/{sid}/mark-paid` `{date, amount?}` → `StreamOut` (adds a manual occurrence, rolls next_due)
- `POST /companies/{id}/streams/{sid}/confirm` `{accept: bool}` → `StreamOut` (accept a "likely" stream, or dismiss = mark not_subscription)

```
StreamOut = {
  id, vendor_name, payee_name, product, category,
  stream_type: "subscription"|"amc"|"one_time"|"prepaid",
  cycle: "monthly"|"quarterly"|"half_yearly"|"yearly"|"biennial"|"triennial"|"irregular"|"custom",
  cycle_months, expected_amount, avg_amount, monthly_equivalent, currency,
  last_paid_date, next_due, anchor_day,
  status: "active"|"due_soon"|"overdue"|"charge_missed"|"stopped"|"cancelled"|"amc_lapsed"|"one_time"|"needs_confirm"|"dismissed",
  confidence (0-100), auto_renew, paid_from, owner_name, pay_url, reminder_on, notes,
  is_user_modified, occurrences_count, sources: ["bank","tally","manual"], first_seen, flags: [str]
}
Occurrence = {id, date, amount_paid, amount_gross, taxable, gst, tds, fees, currency, fx_amount, payment_mode, invoice_no, period_from, period_to, sources: [str], raw_description}
```

## Needs attention (questions)
- `GET /companies/{id}/questions?open=true` → `[Question]`
- `POST /companies/{id}/questions/{qid}/answer` `{choice, text?}` → `{question, stream?: StreamOut}`

```
Question = {id, kind: "vendor"|"cycle"|"split"|"stopped"|"bundle", prompt, context: {payee, amount, dates[], ...},
            options: [{key, label}], stream_id?, answered, answer, created_at}
```
Answering a `vendor` question with a product creates a customer-scoped alias so the same payee is never asked again.

## Upcoming
- `GET /companies/{id}/upcoming?days=90` → `[{month, total, items:[StreamOut+{due}]}]`

## Vendors (catalog, read-only in v1)
- `GET /vendors?q=` → `[{id, key, name, category, default_cycle, variable, is_reseller}]`

## Errors
`{detail: "plain English message"}` with 4xx.
