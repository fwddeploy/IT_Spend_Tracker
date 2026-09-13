# API v2 additions (on top of docs/API.md)

All existing routes stay. New/changed routes below. Auth is now mandatory on every `/api` route except `/api/auth/*` and `/api/health`.

## Auth (email + password, cookie session)
- `POST /api/auth/register` `{name, email, password, company_name}` → creates user + first company + membership(role=owner) → sets session cookie → `{user, companies}`
- `POST /api/auth/login` `{email, password}` → cookie → `{user, companies}`
- `POST /api/auth/logout` → 204
- `GET /api/auth/me` → `{user: {id, name, email}, companies: [{id, name, role}]}` (401 if not logged in)
- `POST /api/auth/invite` `{company_id, email, role}` → creates the user if missing with a one-time password returned in the response (POC: no email sending) → `{email, temp_password, role}`
- Roles: `owner` (everything), `accountant` (edit lines, upload, answer), `viewer` (read only). Every company-scoped route checks membership; 403 otherwise. `GET /companies` returns only the user's companies.
- If `APP_ACCESS_KEY` is still set it is honoured in addition (header), for scripts.
- Sessions: signed cookie `it_session` (itsdangerous), 30 days. Passwords: bcrypt via passlib.

## Company settings
- `GET /api/companies/{id}/settings` → `{name, gstin, fy_start_month, owner_phone, owner_email, accountant_email, whatsapp_enabled, email_enabled, reminder_days_before: {monthly:5, quarterly:10, yearly:30}, weekly_digest_day: "mon"|null, short_name}`
- `PATCH /api/companies/{id}/settings` (same fields) → settings
- `DELETE /api/companies/{id}` (owner only) → 204; cascades everything (rows, occurrences, streams, questions, aliases, reminders, batches, accounts, memberships).

## Hidden payees / learned answers (undo)
- `GET /api/companies/{id}/aliases` → `[{id, pattern (display: the payee text), vendor_name, product, created_at, hidden: bool}]`
- `DELETE /api/companies/{id}/aliases/{alias_id}` → 204 and re-runs the engine.

## Reminders
- `GET /api/companies/{id}/reminders?days=30` → what would go out: `[{stream_id, vendor_name, product, amount, due, days_before, channel: ["whatsapp","email"], will_send_on}]`
- `POST /api/companies/{id}/reminders/send-now` `{stream_id}` → sends immediately via configured channels → `{sent: [{channel, to, ok, error?}]}`
- `GET /api/companies/{id}/reminders/log?limit=50` → `[{id, stream_id, vendor_name, channel, to, sent_at, status, message}]`
- Scheduler: a background loop inside the app (APScheduler, every hour) that, for every company with channels enabled, finds streams with `reminder_on` whose `next_due - today` equals a configured `days_before` (or is overdue and not reminded in 7 days), sends, and logs (dedupe on stream+due+channel). Also `POST /api/internal/reminders/run` (access-key or owner) to trigger manually.
- Channels: WhatsApp via Meta Cloud API (`WA_PHONE_NUMBER_ID`, `WA_TOKEN`, `WA_TEMPLATE_NAME` env; text-message fallback for POC if template unset), email via SMTP (`SMTP_HOST/PORT/USER/PASS/FROM`). If env not set, the send is logged with status `skipped_not_configured` and the UI says so.
- Message text (WhatsApp/email body): "IT Tracker · {company short name}\n{vendor} – {product}\n₹{amount} due {due date} ({days} days)\nPay: {pay_url or 'ask accountant'}\nReply PAID when done." (POC: no inbound handling.)

## Owner share
- `GET /api/companies/{id}/share-text` → `{text}`: a 6–8 line WhatsApp-ready summary (going out this month, monthly-equivalent, next 5 dues). Frontend opens `https://wa.me/?text=...`.

## Export
- `GET /api/companies/{id}/export.xlsx` → Excel with sheets: Lines, Upcoming (12 months), Payments (occurrences), Questions. Content-Disposition attachment.

## FY view
- `GET /api/companies/{id}/dashboard?fy=2026` → same shape as month view but `period: "FY 2026-27"`, `cash_out_period` = sum of dues Apr 2026–Mar 2027 (+ actuals for past months), `calendar` = those 12 months. `fy_start_month` from settings.

## Streams — new fields in StreamOut
- `rcm_gst` (float|null): 18% of expected for foreign no-GST vendors, else null.
- `quantity` (int|null), `unit_price` (float|null) when inferable.
- `fy` (string|null) of the last occurrence's service period ("2026-27").
- `flags_human` (list[str]) — plain-English versions of flags.
- `supplier_history` (list[str]) — payees seen over time when the supplier changed.
- `cash_breakdown` stays on dashboard.

## Questions — new kinds
- `bundle`: known reseller, product unknown, amount ≥ ₹5,000: options = reseller's product list + fingerprint hits + "Split into several" (posts `{choice:"split", items:[{vendor_key, product, amount}]}`).
- Bulk answer: `POST /api/companies/{id}/questions/answer-bulk` `{answers:[{question_id, choice, text?}]}` → runs the engine once → `{answered: n, engine: EngineSummary}`.

## Upload additions
- form field `pdf_password` (optional) used for password-protected PDF statements.
- response adds `detected_bank` (e.g. "HDFC", "ICICI") when recognisable from the header rows, and `hint` (string) when 0 rows were imported ("This statement was already uploaded").

## Audit
- `GET /api/companies/{id}/events?limit=100` → `[{id, at, user, action, target, detail}]`; written by patch/mark-paid/confirm/answer/upload/settings/delete-alias.
