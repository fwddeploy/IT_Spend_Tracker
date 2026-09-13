# Review B — browser walk-through (accountant on desktop, owner on phone)

## What worked
Create company → upload HDFC statement (378 rows, format detected) → upload Tally register → re-upload same file (0 new) → junk file gives plain-English error → answer questions (unknown vendor, stopped) → edit line (owner, pay link, notes) survives reload → mark paid rolls due date → add licence manually → filters/search → upcoming 90/180/365 → home counters navigate correctly → company switch follows on all pages → refresh mid-way restores filter + drawer → empty company shows helpful empty states → no JS errors, no unexpected 4xx/5xx.

## Bugs (severity · fixed?)
1. Blocks demo · Mark paid re-ran the engine and turned a yearly line "irregular", monthly-equivalent ×12, paid-from blank → FIXED in backend (mark paid confirms cycle/amount/paid-from).
2. Annoying · Headline "going out" ≠ current-month calendar bar → FIXED (bar = headline; breakdown paid/still due/estimate returned).
3. Annoying · "Previous imports" never refreshed → FIXED (frontend).
4. Annoying · Tab escaped the drawer; no focus trap → FIXED.
5. Annoying · Phone: Lines/Upcoming hid amount/due/status → FIXED (cards ≤ 640 px; topbar compacted; tap targets ≥ 32 px).
6. Annoying · Company switch left a dead drawer → FIXED.
7. Annoying · Add-licence categories didn't match engine categories → FIXED.
8. Cosmetic · Category/history bars rendered empty (inline span) → FIXED.
9. Cosmetic · Misaligned big-number cards → FIXED.
10. Cosmetic · Junk-file error stacked on stale success → FIXED.
11. Cosmetic · Cancelled lines showed stale due date → FIXED.
12. Cosmetic · Raw flag keys → humanised.
13. Cosmetic · ISO dates in question prompts → FIXED (backend).
14. Cosmetic · "need confirm" and "questions" double-count in the upload summary → open (UI could merge into one CTA).
15. Cosmetic · Sync health counted a failed upload → FIXED (backend).

## UX suggestions (ranked)
1. Make "Mark paid" trustworthy (done). 2. One consistent "this month" number (done). 3. Phone-first Home for the owner. 4. Attention banner on Home when questions are open. 5. Upload-page onboarding with bank-specific export steps; default label from source kind. 6. Browser Back should close drawer/filters on phone. 7. Put Mark paid + Pay link at the top of the drawer; hide confidence/flags behind "details". 8. Plain words: "Per month", "Invoice booked in Tally, not yet paid", "Is this a subscription?". 9. Short company name in the top bar. 10. "This statement was already uploaded" wording for duplicate uploads.
