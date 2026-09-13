# Review A — engine + parser attack (fixed in place; tests 32 → 62)

## Parsers
1. Kotak-style CSV with a narrow preamble line lost the whole table (pandas skipped wider rows) → CSV now read with csv.reader and padded.
2. Credit-card "12,000.00 Cr" read as a debit → side read from the amount cell.
3. ISO dates flipped ("2026-04-01" → 4 Jan); "1", "Page 1 of 3", "MARCH 2026" became dates → date-shape check; ISO/yyyymmdd explicit; time parts stripped. Money accepts "Rs. 5,310.00", "₹5,310", trailing minus.
4. Tally Day Book: party rows became credits; ledger continuation rows skipped; payment vouchers named the bank as payee; purchase + payment double-counted → fixed in Excel and XML parsers.
5. Empty file raised the wrong error; empty cells became the string "nan"; HDFC "Chq./Ref.No." not matched → fixed.
6. Verified OK with tests: ICICI CSV with Legends, SBI text dates, Axis totals row, legacy .xls, PDF via pdfplumber, 5000 rows in < 0.5 s.

## Normalizer
7. Wrong payees for MMT/IMPS, IB BILLPAY, NEFT with bank code, SBI TO/BY TRANSFER, cheque "MICR CTS", "ZOOM.US" → "ZOOM.", "USD 54.99" tails, phone-number VPAs, `ME DC SI`, `PCD/`, `ACH/` → all fixed; new modes netbanking/si/card/nach.

## Vendors
8. Over-matching aliases (AZURE TEXTILES, GCP ENGINEERING, SARALA DEVI, COMPUTAXI, KEKASHI SWEETS, NORTON MOTORS, SAP SERVICES; ESET trailing space never matched; MSFT*AZURE hit M365) → anchored patterns.
9. Exclude patterns without boundaries (EMI, RENT, LOAN, UBER, INDIGO, ESIC, INTEREST) → `\b` added; ATM withdrawals added.
10. Fuzzy layer scored 100 on one-word subsets → single-token/anchored aliases excluded from fuzzy.

## Engine
11. Two identical same-day debits collapsed to one (two Zoom seats) → removed; refund matches nearest debit; same/±2-day charges clustered into one billing event.
12. "REVERSAL" credits were excluded before they could cancel a debit → credits never excluded.
13. Month-end anchor clamped to 28 → clamps to actual month length.
14. `fx_amount` never used → banding and price-change use fx when present.
15. Catch-up at a new price mis-read → handled.
16. Licence + AMC where licence is only 2–3× AMC → narration "LICENCE/PERPETUAL" lowers the threshold.
17. `due_dates_in_range` leaked dates before the range / drifted 31st→28th; status with unknown cycle never went overdue → fixed.
18. `date.today()` used inside dedupe ignoring the engine's `today` → parameterised.

## Noticed, not changed
- Yearly stream with one payment 45 days late → confidence 70 (by-design ±30 d tolerance).
- `TPT/AMC Q2/ABC COMPUTERS/HDFC` (remark before payee) → payee "AMC Q2"; narration still resolves to IT AMC.
- Cheque number matching to Tally (rule 2.37) only via amount/date.
- `SERVICE CHARGE` exclusion could hide an IT vendor's AMC service line.
- `4/1/2026` parsed day-first (ambiguous by nature).
