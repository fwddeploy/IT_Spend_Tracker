# Status after v0.2 — everything from the review list, done or noted

Built in this pass (all tested: 107 backend tests on SQLite and on Postgres; browser QA walk of every screen on desktop and phone):

Accounts and safety
- Login with email + password; register creates your company; roles owner / accountant / viewer; invite people from Settings (temp password shown once). Every API call needs a login (or the X-Access-Key header for scripts).
- Settings page: company details, short name, FY start month, owner phone/email, accountant email, reminder channels and days, weekly digest day; hidden payees list with Remove (undo); delete company (type the name).
- Audit log of every change (who did what); Excel export (Lines / Upcoming / Payments / Questions); WhatsApp share text for the owner.
- Alembic migrations on Postgres (fresh DB and adopting a v0.1 DB); non-root Docker image with health check and 2 workers; per-company lock so two uploads can't run the engine at once; upload size/type guards; India-time dates.

Reminders
- Hourly job that finds dues within the configured days (monthly 5 / quarterly 10 / yearly 30, editable), sends WhatsApp (Meta Cloud API) and/or email (SMTP), logs every send, never sends the same reminder twice, re-nudges overdue lines weekly. Preview + "Send test now" + log in Settings. Without env vars set, sends are logged as "not set up on the server yet".

Engine
- Cheque number matching bank ↔ Tally; hardware-only bills become one-time purchases, mixed bills flagged; reseller bills with no product raise a "which product / split it" question; supplier switch (reseller → direct) merges into one line with history; prepaid run-rate = 6-month average; yearly/quarterly due dates keep their usual day; paid-early handling; catch-up payments anywhere in history; FY tag; reverse-charge GST amount; "paid from personal card, not in company books" flag; price-change note ("1,450 → 1,740 on 3 Apr 2026"); seat count inference (10 users × ₹145); reseller directory grown to ~70 names; PDF password support; bank auto-detected from the file.
- Mark paid: keeps the line's cycle and usual due day (paying early or a day late no longer shifts the anchor); the held due date releases when the next real payment appears.

Screens
- Onboarding steps on Upload (how to get Excel from HDFC/ICICI/SBI/Axis/Kotak; Tally Ctrl+E); Home banner for open questions; paid / still due / estimate breakdown; Month ↔ FY toggle; drawer reordered (Mark paid and Pay now first, plain-English details); bulk mark-paid and bulk answers; plain words everywhere; phone layouts.

Still not in (by choice, small)
- Inbound email address and WhatsApp intake of bill photos, GSTR-2B pull, Zoho Books / Microsoft 365 connectors — the next pipes from the plan.
- Money stored as float (fine for INR at this scale; switch to Numeric when convenient).
- Sample data has no PDF statement; PDF parsing is tested on generated files only — verify on a real bank PDF at the first pilot.

Demo login: demo@ittracker.local / demo1234. Env vars for WhatsApp: WA_PHONE_NUMBER_ID, WA_TOKEN, WA_TEMPLATE_NAME (optional). Email: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM. Also SECRET_KEY (set a long random string in production).
