# Review C — product + engineering gap review (read-only)

Verdict: the engine core is real (TDS/GST relations, forex folding, refunds, split payments, Tally booked-not-paid, two headline totals). The product around it was a no-login, no-reminders demo, and the sample company avoided the hard cases (no gateway-only lines, no cheques, no PDF, no personal card, no second company, every reseller line carried a helpful narration).

## 1. User-flow gaps
P0: login/users/roles; reminders never sent (reminder_on stored, no scheduler/sender); onboarding path ("what to upload, how to get it"); password-protected PDF statements; CA multi-client landing.
P1: Excel/PDF export; FY (Apr–Mar) view (fy_start_month unused); bulk actions on questions/lines (each answer re-runs the engine); invoice attachments; seat counts; audit trail; delete company/data; undo for "No/dismiss" (permanent not_it alias); "Due in 7 days" copy vs per-cycle windows (fixed).
P2: negotiation info, per-line reminder schedule, personal-card reimbursement, inbound email + WhatsApp intake.

## 2. Engine gaps vs the research rules
P0: gateway alias learning over-generalised (fixed by anchoring); `P.A.` term regex matched PAYMENT/PARTY (fixed); unanchored exclusions killed real vendors (fixed by review A); cheque-number ↔ Tally matching not implemented.
P1: reseller bundle question is a stub; hardware line exclusion unused; supplier-switch merge not implemented (test enshrines two lines); multi-company shared licence; FY tagging; RCM shown as a flag only; personal-account → Tally journal link half-done; prepaid run-rate = median top-up (should be 6-month average); fx grouping (fixed by A); yearly anchor day; paid-early branch; catch-up mid-history.
P2: LLM fallback; global alias promotion queue; 17-name reseller directory; fingerprints only for Tally.

## 3. Correctness risks
P0: mark-paid/cycle answers froze next_due forever (fixed); any PATCH set confidence=100 (fixed); prepaid double count in cash-out (fixed); overdue items vanished from cash-out (fixed); global mutable Catalog shared across requests (open); concurrent upload+run can interleave delete/insert (open — needs per-company lock); stream_key includes product + amount bucket so identity can change under the user (open).
P1: date.today() vs IST (fixed); Postgres string lengths (fixed for stream names); Float money → Numeric (open); missing indexes; whole file in memory, all sheets parsed (25 MB cap added); ingest dedupe collapsed same-day identical rows (fixed); overdue tile excludes charge_missed; "paid elsewhere" pins active; refund matching (fixed by A).

## 4. Security / prod-readiness
P0: no auth (stop-gap access key added); CORS * (restricted); PII at rest unencrypted, default DB password; no upload limits/type checks (added); no migrations (Alembic still needed).
P1: Docker runs as root, no HEALTHCHECK, single worker with sync routes; no logging config/request ids; no backups; SEED_SAMPLE default 1; /health didn't touch the DB (fixed); no rate limiting.

## 5. Copy
"Engine", "Lines", "Streams", "Sources", "Confidence 83%", raw flags — speak accountant instead; explain what to upload; show the "going out" split (done in API); first-run banner for the sample company; "No" on a confirm should say it hides the payee.

## 6. Top 10 next commits
1. Engine P0 fixes (done: P.A., exclusions, gateway alias; open: cheque↔Tally). 2. Stop freezing next_due / confidence on PATCH (done). 3. Cash-out correctness (done). 4. Auth + company scoping (stop-gap done; real auth open). 5. Reminder job + WhatsApp/email sender. 6. Onboarding wizard + PDF password + upload limits (limits done). 7. Alembic + Numeric + advisory lock + background job. 8. Reseller bundle + hardware exclusion + supplier-switch merge. 9. Copy pass + flag labels + RCM amount. 10. Excel export, FY view, hidden-payees undo, delete company.
