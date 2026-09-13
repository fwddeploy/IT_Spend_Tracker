# Review of v0.1 — what three reviewers found, what was fixed, what is still open

Three independent passes were run on the first build: (A) engine + parsers attacked with realistic bank/Tally files, (B) the whole user flow clicked through in a browser as accountant and as owner-on-phone, (C) a read-only product/engineering gap review against the plan.

## Fixed in this pass

Engine / parsers (A) — 32 → 62 tests
- Kotak-style CSV with a narrow preamble lost the whole table; credit-card "12,000.00 Cr" read as debit; ISO dates flipped day/month; "Page 1 of 3" parsed as a date; "Rs. 5,310.00" not read; HDFC "Chq./Ref.No." column not matched; empty file crashed.
- Tally Day Book: party rows became credits, ledger continuation rows dropped, payment vouchers named the bank as payee, purchase + payment double-counted (Excel and XML).
- Narrations: MMT/IMPS, IB BILLPAY, SBI "TO TRANSFER-…", cheque "MICR CTS", "ZOOM.US", "USD 54.99" tails, phone-number UPI handles, `ME DC SI`, `PCD/`, `ACH/` — all gave wrong payees; fixed.
- Vendor aliases over-matched (AZURE TEXTILES → Azure, SARALA DEVI → Saral, KEKASHI SWEETS → Keka, NORTON MOTORS → Norton…); exclusion words without boundaries (EMI hid YouTube Premium, RENT hid PREMIER INFOTECH); fuzzy layer re-opened the holes. All patterns anchored.
- Two identical same-day charges collapsed to one (two Zoom seats); refunds matched the wrong debit; "REVERSAL" credits were excluded before they could cancel anything.
- Month-end anchor (31st) drifted to the 28th forever; `fx_amount` was never used for USD vendors; catch-up payment at a new price mis-read as a price hike; licence + AMC split threshold; due-date maths for a due date many cycles in the past; status when cycle unknown.

User flow (B)
- "Previous imports" never refreshed; Tab key escaped the line drawer; phone view of Lines/Upcoming hid amount/due/status (now cards); company switch left a dead drawer; manual-add categories didn't match engine categories; category and history bars rendered empty; misaligned big-number cards; junk-file error stacked on a stale success box; cancelled lines showed a stale due date; raw flag keys shown.

Backend fixes from (B) and (C)
- **Mark paid no longer wrecks a yearly line** (re-run turned it "irregular" and inflated monthly-equivalent 12×): marking paid now confirms the line's cycle/amount/paid-from and lets the engine roll the due date.
- **Frozen due dates**: mark-paid / cycle answers / PATCH no longer freeze `next_due` forever; a user-typed due date is honoured until the next real payment arrives, then the engine takes over again. Regression test: mark paid → upload next year's statement → due date moves.
- PATCHing a note or the reminder toggle no longer silently marks a line "confirmed".
- "Going out this month" now counts only live lines, doesn't double-count prepaid top-ups, counts overdue items as due now, and returns a breakdown (paid so far / still due / estimate); the current-month calendar bar equals the headline.
- "Due in 7 days" tile is now a true 7-day count.
- Two identical rows in one file are two payments (dedupe key was collapsing them).
- Learned aliases are anchored (answering one Razorpay question no longer relabels every Razorpay line).
- Term regex `P.A.` no longer matches PAYMENT/PARTY (which made random single payments "yearly").
- Upload guards: 25 MB cap, real-Excel/PDF magic-byte check, extension whitelist, internal errors no longer leaked to the user.
- Dates use India time (server may be in UTC); Postgres string-length safety; sync-health ignores failed uploads; question prompts show "13 Apr 2026" not ISO.
- Optional access key (`APP_ACCESS_KEY`): if set, every API call must carry it; the page asks once. CORS restricted to the dev origin.
- `/api/health` now touches the DB.

## Still open (from review C), in priority order

P0 — before a real pilot
1. Real login / users / roles (the access key is a stop-gap; a CA with two clients needs proper scoping).
2. Reminders are not sent yet: `reminder_on` is stored, no scheduler, no WhatsApp/email sender.
3. Onboarding help on the Upload page (how to download Excel from HDFC/ICICI/SBI; Tally Ctrl+E), PDF password field.
4. Cheque-number matching bank ↔ Tally (`CHQ 000412`) — only amount/date rescue today.

P1 — first month of pilots
5. Reseller bundle question (one bill = Seqrite + M365) and hardware line-item exclusion are stubs.
6. Supplier-switch merge (reseller yearly → direct monthly) — currently two lines.
7. Prepaid run-rate should be a 6-month average, not the median top-up.
8. Excel/PDF export, FY (Apr–Mar) view, hidden-payees list with undo, delete company.
9. Alembic migrations, `Numeric` money columns, per-company lock around engine runs, background job for big uploads.
10. Copy pass: "Engine" → plain words, flag labels, RCM amount shown, "Share on WhatsApp" link for the owner.

P2
- Multi-company shared licence, LLM fallback for unknown payees, global alias promotion review queue, larger reseller directory, per-seat fingerprints for M365/Seqrite.

The three full reports are in `docs/review/`.
