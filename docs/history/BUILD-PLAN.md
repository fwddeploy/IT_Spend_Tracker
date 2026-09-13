# IT Tracker for MSME / Manufacturing — Build Plan v2

Level: complete plan, written as "this category → these cases → this is what we do". Built from three research passes (market, integration options, engine logic). The three raw research reports are in the `research/` folder next to this file.

Goal: one tool that shows a factory every software / licence they pay for, what goes out this month, what is due next, with reminders and pay links — pulled in with zero install and near-zero typing, covering 90–95% of real cases before the first deployment.

---

## 0. What changed from v1 (read this first)

- Account Aggregator (auto bank feed) is OUT. It only works for individuals and sole-proprietor accounts, not Pvt Ltd / partnership current accounts, and you must be an RBI-regulated company to use it. Bank statement upload/forward is the bank path.
- Reading Gmail directly is expensive: Google demands a yearly security audit (CASA, ~₹50k–1.5 lakh + weeks of time). So v1 uses a forwarding rule to our own address instead. Outlook is easier (admin clicks Allow once). Gmail direct-connect comes later.
- New strong source found: GST portal (GSTR-2B). Every purchase from an Indian GST-registered seller (resellers, Google India, AWS India, Zoho, Tally partners, SolidWorks VARs…) shows up there with vendor name, GSTIN, invoice number, date and amount. Customer enables "API access" once on the GST portal and enters an OTP monthly — their CA already does this for ClearTax/Zoho. This becomes a main pipe.
- Microsoft 365 has a real API for licence counts and renewal date (admin clicks Allow once). Google Workspace, Adobe, Autodesk do not — email/invoice is the only way.
- WhatsApp is both an intake channel (accountant sends bill photo) and the reminder channel. Cost ≈ ₹0.12–0.40 per reminder.
- Nobody in the market does this for Indian factories. Closest models to copy: Hudled (accounting-sync tracker at $19–79/mo), ManageEngine SaaS Manager Plus (invoice OCR + mailbox), LowerMySubs (statement upload with confirm).
- Engine now has exact rules for 48 tricky situations and 52 test cases (see `research/3-engine-logic-and-test-cases.md`).

---

## 1. Where we stand in the market (high-level)

- Big tools (Zluri, Zylo, Torii, Productiv, CloudEagle, Spendflo): built for 250+ staff tech companies, $10k–40k/year, discover apps via SSO logs and browser extensions. Useless in a factory (no SSO, CAD/ERP are desktop apps).
- Small tools (Substly, Cledara, Hudled, TrackMySubs): cheaper but need Xero/QuickBooks, their own cards, or manual entry. None know Tally, INR, GST, resellers, or perpetual licence + AMC.
- India (Volopay, EnKash, Kodo, RazorpayX): corporate-card products. They only see card spend; factories pay resellers by NEFT/cheque, so they miss most of it.
- Our gap: Tally/GST-ledger discovery + reseller invoice reading + on-prem licence & AMC dates + INR/GST totals + WhatsApp to the owner + zero-install + flat ₹ price. Nobody has all of it.
- Proof the pain is real: SolidWorks makes you pay all missed years to reinstate a lapsed subscription; Autodesk makes you re-buy; SAP B1 AMC is 18–22% of licence per year (₹3–3.5 lakh/yr for 10 users). One missed renewal costs more than a year of our tool.

---

## 2. The one design rule

Pipes → Engine → Screen.

- Pipes: every way data can come in. Each pipe outputs the same simple row: date, who was paid, how much, bill number, period/due date if known, paid or not, source.
- Engine: recognise the vendor → remove duplicates → spot repeating pattern → build one line per subscription with next due date and status.
- Screen: this-month total, line items, upcoming dues, reminders, pay links.

Adding a new software or bank later = adding a pipe. Engine and screen never change.

---

## 3. Category A — Getting the data in (zero install)

Rule for the whole category: nothing to install, ever, in v1. Every path is "click Allow once", "set one forwarding rule", or "send a file/photo".

Think of it as a trust ladder. Customer starts at Level 0 on day 1 and climbs as they trust us. Every level works on its own.

### Level 0 — Send us anything (day 1, no permissions at all)
- Case: they have last 12–24 months of bank statement → download Excel from net banking, upload. Engine finds recurring software payments. This alone gives a first dashboard in 10 minutes.
- Case: reseller bill arrives on WhatsApp / paper / email → accountant forwards the photo or PDF to our WhatsApp number or unique email address. We read it (OCR + AI) and add the line.
- Case: Tally / Busy / Marg / any software → accountant opens Purchase Register (or the "Software / Computer expenses" ledger), presses Ctrl+E (export Excel/XML) or Ctrl+M (email) and sends to our unique address. Once a month, 2 minutes. Tally cannot schedule this itself — it's a button press.
- Case: they know a licence we didn't find → manual add, 30 seconds.

### Level 1 — One forwarding rule (5 minutes, one time)
- Case: Gmail / Google Workspace → they add our unique address `bills-xxxx@in.ourtool.in` as a forwarding address (we receive the confirmation code and show it to them), then one filter: "from Microsoft, Google, Adobe, Autodesk, Zoho, AWS, GoDaddy, bank alerts → forward". From then on every invoice and bank/card alert email lands with us automatically.
- Case: Outlook / Microsoft 365 → same rule, BUT new M365 tenants block auto-forward outside the company by default. Their admin must switch it on (we give a 3-step guide), or they forward by hand monthly, or use Level 3 instead.
- Case: bank emails a monthly e-statement (most do) → include the bank in the filter; we get the statement PDF every month. They give us the PDF password once.
- Case: they don't want any rule → stay at Level 0 (manual forward when a bill comes). Still works.

### Level 2 — GST portal consent (10 minutes, OTP once a month)
- What it gives: every purchase invoice filed against their GSTIN by any Indian GST-registered seller — vendor name + GSTIN, invoice number, date, amount, GST. This catches all reseller bills (SolidWorks VAR, Tally partner, Seqrite dealer, Microsoft CSP), Google India, AWS India, Zoho, GoDaddy India, Airtel — without any invoice being sent to us.
- Case: customer or their CA logs into gst.gov.in → My Profile → Manage API Access → Enable (30 days) → in our app enter GSTIN + GST username → OTP → done. Every month we pull the new GSTR-2B (available on the 14th). OTP again after 30 days — the CA already does this monthly for ClearTax/Zoho, so it's familiar.
- Case: vendor is foreign and not GST-registered in India (Adobe on card, Notion, Figma, DigitalOcean, Microsoft direct from Singapore) → does NOT appear in GST data. Covered by email (Level 1) or bank statement (Level 0).
- Case: vendor files GST late → shows a month late. Bank/email fills the gap meanwhile; engine merges when it arrives.
- What we do: sign up with a GSP (Sandbox, Masters India, ClearTax, etc.). Small monthly fee + a few rupees per call — get quotes.

### Level 3 — Click "Allow" on their cloud accounts (1 minute each)
- Case: Zoho Books → "Connect Zoho" → login → Allow. We pull bills, expenses, vendor payments daily. Cleanest possible source.
- Case: Microsoft 365 → their admin clicks our consent link → Accept. We read licence counts (bought vs used) and the renewal date directly. Also gives Outlook invoice-mail access if they want.
- Case: Google Workspace → no licence API exists. Invoice email (Level 1) is the source.
- Case: Adobe, Autodesk, SolidWorks, Tally, Quick Heal → no API. Invoice email / GST data / reseller bill is the source.
- Case: AWS / Azure → cost APIs exist (need an admin role assignment). Later; monthly invoice email is enough for v1.

### Level 4 — Later, install-based (only when a customer asks)
- Tally live connector (small program beside Tally, nightly sync via Tally's local port 9000) → exact due dates without anyone pressing export.
- PC agent listing installed software → catches perpetual licences bought years ago and "10 seats bought, 4 used".
- Gmail direct connect (after we pass Google's CASA audit).

### Coverage check for Category A
- Money side: bank statement upload (works for 100% of companies) + card alerts by email.
- Detail side (who/what/when due): GST data (all Indian-billed vendors) + invoice emails (foreign-billed vendors) + WhatsApp photos (paper bills).
- Books side (optional): Tally export / Zoho connect.
- Miss: cash payments never recorded anywhere (rare for software) and licences bought years ago with no recent payment (ask once at onboarding: "any software you own outright?").

---

## 4. Category B — How the money actually leaves

- Case: company bank NEFT / RTGS / IMPS → statement line shows the beneficiary name (often the reseller, not the software brand). Rule: take the name, send to vendor recognition (Category C).
- Case: company card, auto-charge (Microsoft, Adobe, Google, AWS, Zoom) → line shows a merchant code like `MSFT*E0100…`, `GOOGLE *WORKSPACE`, `ADOBE SYSTEMS SOFTWARE IRELAND`. Rule: alias table maps these directly; mark as auto-renew.
- Case: standing instruction / NACH (`SI …`, `ACH D- AIRTEL`) → Rule: auto-renew; reminder text says "will be charged on…" (risk is card expiry, not forgetting).
- Case: UPI (`UPI/…/tallysolutions.rzp@hdfcbank/…`) → Rule: the VPA usually contains the merchant name; parse it.
- Case: payment gateway hides the vendor (`RAZORPAY`, `PAYU*`, `CCAVENUE*`, `STRIPE*`, `PAYPAL *`) → Rule: strip the gateway prefix and try the remainder; else look for an invoice email or GST/Tally entry with the same amount within a few days; else ask the user once and remember (gateway + amount + day-of-month).
- Case: owner pays from personal card / UPI (very common: Adobe, Canva on MD's card) → Rule: allow a second "personal" account/statement; show "paid from MD personal card" and warn "not in company books" if no Tally/GST entry.
- Case: cheque to local vendor (`CHQ 000412`, no name) → Rule: resolve via Tally payment voucher with same cheque number, or GST entry with same amount, or ask once.
- Case: cash → only in Tally. Rule: Tally is the source of truth for these lines.
- Case: foreign currency on card (USD 54.99 → ₹4,612 one month, ₹4,701 next, plus a separate "FOREIGN CURRENCY MARKUP" line) → Rule: group on the USD amount if shown; else allow ±8% amount wobble for USD-flagged vendors; fold the markup line (same day, ≤5% of main debit) into the same payment as fees.
- Case: bank's own charges (`CONSOLIDATED CHARGES`, `SMS ALERT CHG`) and government payments (`CBDT`, `OLTAS`, `GST PMT`, `MCA21`, `BHARATKOSH`) → Rule: excluded up front, never shown.
- Case: money coming IN from Razorpay (they sell online) → Rule: only debits are candidates; credits are considered only as refunds.

---

## 5. Category C — Recognising who the vendor is

Order of attempts, cheapest first. Every match records how it was made so we can score confidence.

- Step 1 – Clean the text: uppercase; strip bank prefixes (`POS`, `VIN/`, `UPI/`, `NEFT-`), transaction ids, dates, card fragments, city suffixes (`DUBLIN`, `SINGAPORE`), `PVT LTD/LLP/LTD`; strip gateway prefixes but keep the rest.
- Step 2 – Alias dictionary (exact/prefix/regex): `GOOGLE *WORKSPACE|GSUITE` → Google Workspace; `MSFT|MICROSOFT … E0` → Microsoft 365; `ADOBE` → Adobe; `AMAZON WEB|AMAZON INTERNET SERVICES|AISPL` → AWS (variable); `TALLY SOLUTIONS` → Tally TSS/licence; `DEFMACRO` → ClearTax; `WALKOVER` → MSG91 (prepaid); `GREYTIP` → GreytHR; `QUICK HEAL|SEQRITE`; `GODADDY|DNH*GODADDY`; `ZOHO CORP|ZOHO*`; `BHARTI AIRTEL`, `RELIANCE JIO`… Each row carries: category, default cycle (monthly/yearly), variable-amount yes/no, currency, foreign-or-Indian entity, typical TDS.
- Step 3 – Reseller list: names of Tally partners, SolidWorks VARs (Cadspro, Beacon, Conceptia, EGS…), Autodesk partners (Capricot, Arkance…), Seqrite dealers, Microsoft CSPs, scraped from the vendors' public partner directories → each reseller row says "sells: tally, seqrite, m365…" so a reseller name immediately suggests a product menu.
- Step 4 – Fuzzy match against the dictionary and against this customer's already-confirmed payees (ignore filler words like INFOTECH, TECHNOLOGIES, SOLUTIONS, INDIA). Plus amount fingerprint: ₹5,310 = Tally TSS Silver, ₹15,930 = TSS Gold, multiples of a known per-seat price → propose the product as a "guess".
- Step 5 – Cross-source lookup: unknown bank payee → search invoice emails / GST data / Tally rows for the same amount within ±15 days (email) or ±60 days (Tally). This is how gateways and cheques get solved.
- Step 6 – AI (LLM) only for still-unknown payees worth ≥ ₹2,000 total or seen ≥ 2 times: "is this a software/IT vendor, what product, what cycle, is it a reseller?" Accept only if confident; cache the answer globally.
- Step 7 – Ask the user once, pre-filled: "₹11,800 to SHREE INFOTECH every April — is this (a) Tally TSS (b) antivirus (c) IT AMC (d) hardware (e) other?" Answer saved for this customer; if many customers confirm the same string, promote to the global dictionary.
- Rule for resellers: streams are keyed by product, not payee. "Tally TSS via Shree Infotech" and "Tally TSS direct" merge into one line. Reports can show by product (what you use) and by payee (who you pay).
- Rule for reseller bills with many items (Seqrite + M365 + Tally on one bill): if we have line items (invoice PDF, Tally register) → one line per item. If only the bank amount → one "bundle" line and ask once to split (suggest products from amount fingerprints).
- Rule for hardware mixed in (laptops + Windows + AV on one bill): items with hardware words/HSN codes are excluded; only "licence, subscription, renewal, AMC, support, annual, cloud, user" lines become candidates.
- Non-IT lines (raw material, salary, rent) are dropped early; user never sees them.

---

## 6. Category D — Billing patterns (how the engine decides "this repeats")

Grouping key: (company, vendor, product, amount band, currency). Never group on amount alone (₹2,360 to Zoho and ₹2,360 to Canva are two lines).

- Case: monthly (gaps 27–34 days) → MONTHLY. Quarterly (84–98) → QUARTERLY. Half-yearly (170–195) → HALF_YEARLY. Yearly (340–395) → YEARLY. 2-year (700–760), 3-year (1060–1130) → multi-year. Rule: use the MEDIAN gap (one late payment doesn't break it), then snap to the nearest cycle.
- Case: payment seen only once → "candidate" with the vendor's default cycle from the dictionary (TSS → yearly, GoDaddy → yearly, AWS → monthly). If the invoice/Tally text says "1 year / 12 months / 01-Apr-25 to 31-Mar-26" → use it. Ask the user only if vendor unknown AND amount ≥ ₹5,000.
- Case: seen twice → cycle = that one gap snapped; show as "looks yearly — confirm?" (one tap).
- Case: seen 3+ times → mature; auto-accept if confidence score is high (below).
- Case: perpetual licence + yearly AMC (Tally ₹22,500 then ₹5,310 every year; SolidWorks ₹2 lakh then ₹40k/yr; SAP B1) → Rule: a payment ≥3× the later repeating amount, occurring first, is tagged ONE-TIME LICENCE (no due date); the smaller repeating one becomes the AMC/subscription line. If AMC stops, status is "AMC lapsed" (software still works), not "cancelled".
- Case: 3-year prepaid (Seqrite 3-yr key, domain 2-yr, Hostinger 48-month promo) → cycle = that; monthly-equivalent = amount ÷ months; next due = date + term; warn "renewal likely at full price" for promo vendors.
- Case: usage-based (AWS, Azure, Exotel, printer rental, Airtel) → amounts vary every month. Rule: vendor flagged "variable" → tolerance ±60% around last-3-month median; cycle from dates only; show "≈ ₹X/month (avg)"; never flag a price change.
- Case: prepaid credits / top-ups (SMS, WhatsApp API wallet, Google Ads) → irregular dates, round amounts. Rule: type = PREPAID; no due date; show monthly run-rate (last 6 months ÷ 6) and "top-up roughly every N days".
- Case: seat count change (M365 ₹1,450 → ₹1,740 and stays) → same line; note "quantity changed on <date>"; expected amount = latest.
- Case: price hike (≤ +50%, persists) → same line; note "price changed A → B"; predict using LAST amount, not average.
- Case: late payment / date drift → tolerance: monthly ±5 days, quarterly ±10, half-yearly ±15, yearly ±30, 3-yearly ±45. Anchor day = median day of the last 3 payments.
- Case: paid early (renewed a month before expiry) → counts as this cycle's payment; next due = previous expected due + cycle when invoice shows validity; else payment date + cycle.
- Case: two months paid together (one debit = 2× monthly after a missed month) → treated as catch-up; no new line, no price-hike flag.
- Case: partial / split payment (₹2,00,000 + ₹36,000 same day for a ₹2,36,000 invoice; or ₹23,600 twice 6 weeks apart for ₹47,200) → if debits within 45 days sum to a known invoice (±2%) → merge into one payment; note "paid in 2 parts".
- Case: refund / reversal (credit same amount within 30 days) → cancel that payment; if no later charge → CANCELLED (refunded). Two identical debits same day + one credit → keep one.
- Case: trial → paid (₹1–₹2 authorisation, then real charge) → ignore debits ≤ ₹5; backdate "since" to the auth date.
- Case: supplier switched (M365 via reseller for 2 years, then card `MSFT*`) → same product, old stream stops within a cycle of new one starting, amount within ±25% → merge with note "supplier changed"; old line is "closed", not "stopped".
- Case: same vendor, two products (Zoho Books monthly ₹2,360 + Zoho Mail yearly ₹11,800) → amount bands keep them as two lines.
- Case: rounded UPI vs exact invoice (₹5,300 vs ₹5,310) → match within ±2% or ₹50.

Confidence score (0–100): +30 if 3+ payments (+15 if 2); +25 × share of gaps that fit the cycle; +15 if amounts stable (or dates fit, for variable); +15 if known vendor and cycle matches its default; +10 if invoice/Tally text says renewal/subscription/period; +5 if auto-pay mode; −20 if last payment older than 2 cycles; −10 if resolved only through a gateway guess.
- ≥75 → auto-accept (shown as confirmed).
- 45–74 → "likely — confirm?" one tap.
- <45 → candidate in "Unclassified payments"; ask only if yearly value ≥ ₹5,000 or AI says it's IT-ish.
- Any user edit → locked; engine never overrides it again.

---

## 7. Category E — Tax and currency oddities (why the bank amount ≠ the invoice amount)

- Case: Indian vendor, GST 18% → invoice ₹10,000 + ₹1,800 = bank debit ₹11,800. Rule: when matching invoice ↔ bank, test bank = total, bank = taxable × 1.18, bank = taxable (±₹2). Store taxable, GST, paid separately. Show gross cash-out by default; "net of GST credit" as an option.
- Case: TDS deducted (invoice ₹1,18,000; TDS 2% on ₹1,00,000 = ₹2,000; bank ₹1,16,000) → Rule: if bank is short by exactly 1%, 2%, 10% (or 20%) of taxable value (±₹5) → match and record TDS. Group recurrence on the GROSS amount so that when TDS starts mid-year (vendor crosses ₹50,000/FY) it doesn't look like a price cut.
- Case: foreign vendor, no Indian GST (Notion, Figma, DigitalOcean, Namecheap) → bank debit is the foreign amount only; company pays 18% IGST separately under reverse charge. Rule: tag "RCM"; show "18% GST payable by you ≈ ₹X (credit claimable)"; never try to match the GST challan to the vendor.
- Case: foreign vendor WITH Indian GST registration (AWS India, Google India, Adobe Ireland for India, Zoom) → GST is on the invoice; normal case.
- Case: TDS challan to government later (`TIN NSDL`, `CBDT`) → excluded.
- Keep tax rates (194J threshold ₹50,000/FY, 2%/10%, RCM 18%) in a config table reviewed every Budget; confirm with a CA.

---

## 8. Category F — Same bill seen twice, entries lagging, many companies

- Case: same AWS bill appears in email (3-Apr), bank (4-Apr) and Tally (booked 30-Apr) → Rule: one payment. Unique by (vendor, invoice number) when known; else (vendor, amount ±2%, date window). Windows: email↔bank ±15 days; Tally↔bank ±60 days; GST↔bank ±60 days. Merged record keeps: date = bank (cash truth), amount = bank, product/period = invoice, ledger/category = Tally. Never count spend twice.
- Case: Tally entry with no bank line within 60 days → "booked, not yet paid" (this is the "going to be cut this month" view).
- Case: accountant posts bills weeks late → recurrence and due dates always come from bank/invoice dates, never Tally booking dates.
- Case: two companies / branches under one owner (two GSTINs, one M365 paid by company A) → every row carries company id; lines are per company; same product in two companies → flag "possibly shared"; user can mark "paid by A, used by A+B" and reports split by seats.
- Case: CA managing 20 clients → multi-company switcher; one login.
- Case: financial year → yearly lines tagged by FY of service period; reports offer FY (Apr–Mar) and calendar views; March/April renewals highlighted as "FY-end renewals".

---

## 9. Category G — What the user sees (and the statuses behind it)

Two totals, always side by side, because mixed cycles confuse people:
- "Cash going out this month" = sum of every line whose due date falls this month (actual) + average for variable/prepaid lines + anything already paid this month. Gross, including GST.
- "Monthly-equivalent IT spend" = each line's amount ÷ months in its cycle (yearly ÷ 12, quarterly ÷ 3…). The true burn rate that doesn't spike in March.
- Also: annualised (×12), split by category / company / vendor / cycle, and "next 12 months calendar" so FY-end clustering is visible; "committed" (auto-renew/contract) vs "discretionary" (manual pay).

Line-item statuses:
- ACTIVE — last payment within one cycle + grace.
- DUE SOON — next due within window (monthly 5 d, quarterly 10 d, yearly 30 d, 3-yearly 45 d).
- OVERDUE (manual pay) / CHARGE MISSED (auto pay) — past due + grace (monthly 7 d, quarterly 15 d, yearly 30 d).
- STOPPED — one full extra cycle passed with no payment; shown in a separate "Stopped" list to confirm "cancelled" vs "forgot".
- CANCELLED — refund seen or cancellation email.
- AMC LAPSED — for perpetual + AMC products.
- ONE-TIME — licence/hardware; no due date.
- NEEDS CONFIRM — engine guess waiting for one tap.

Next due date, in order of trust: invoice "valid to" date + 1 → else last paid + cycle (anchored to the usual day) → for prepaid: "typical gap N days, last top-up X days ago". For manual-pay lines falling on Sunday, show the prior Friday as "pay by".

Screens:
- Home: the two totals, count of active licences, count due in 7 days, the next 5 dues.
- Line items table: vendor, product, category, cycle, amount, next due, status, paid-from (company bank / card / MD personal), source, internal owner.
- Upcoming: next 90 days month by month.
- Needs-attention inbox: every guess waiting for yes/no — designed so the accountant clears it in 2 minutes a week.
- Reminders: WhatsApp + email; yearly 14 & 7 days before, monthly 5 & 1 days; "late" alert; weekly digest to owner; per-line on/off.
- Pay link per line: vendor portal (Microsoft admin billing, Adobe, Google, Zoho, Tally renewal page) or reseller's UPI / bank details / phone. "Pay now" opens it; "Mark paid" tick. No money moves through us in v1.
- Export to Excel / PDF; multi-company switcher for CAs; sync-health page ("bank statement last received 3-Aug — upload the new one").

---

## 10. Category H — Who uses it, pricing, how it sells

- Owner / MD: one number and the next dues, on phone, via WhatsApp. Reads, doesn't type.
- Accountant / accounts clerk: does the uploads, forwards bills, clears the needs-attention inbox, marks paid.
- Outside CA: manages many companies; likely both a user and a sales channel (CAs already have the GST login and Tally files).
- Resellers (Tally partners, CAD VARs, Seqrite dealers): they chase renewals anyway; potential channel — the tool reminds their customers to pay them.
- Pricing shape (to decide): flat per company per month, ₹999–2,999 range, tiered by number of tracked lines or companies; CA bundle for many companies. Never per employee, never "contact sales". Free tier for up to ~5 lines to get in the door.
- Positioning: "know your IT bill before it hits" — sell the missed-renewal pain (SolidWorks back-pay, Autodesk re-buy, TSS lapse) more than "savings".

---

## 11. Build order

Phase 0 — Design freeze (1 week)
- Lock this document; paper screens; name; pricing tiers; WhatsApp provider; GSP choice.

Phase 1 — Engine + file intake (weeks 1–3)
- Row normaliser; vendor dictionary v1 (300 vendors + reseller list scraped from partner directories); recurrence engine; confidence scoring; the two totals.
- File import: bank statement Excel/CSV/PDF (templates for SBI, HDFC, ICICI, Axis, Kotak, Yes, IndusInd, BoB, PNB), Tally Purchase Register Excel/XML, generic column auto-detect.
- Invoice reader: PDF/image → fields (vendor, GSTIN, items, amount, GST, period).
- Manual add/edit. Test set of 52 cases passes ≥90% without asking.

Phase 2 — Inbound channels + screens (weeks 3–6)
- Unique inbound email address (Postmark / SendGrid inbound) + Gmail/Outlook forwarding guides.
- WhatsApp number (Meta Cloud API via BSP): receive bills, send reminders.
- Home, line items, upcoming, needs-attention inbox, pay links, Excel/PDF export.

Phase 3 — Consent-based pipes (weeks 6–8)
- GSTR-2B via GSP (enable API access + OTP flow).
- Zoho Books connect; Microsoft 365 admin consent (licences + renewal date).
- Multi-company + CA view.

Phase 4 — First deployments (weeks 8–12)
- 5–10 factories via 2–3 CAs / resellers; sit with the accountant; every wrong match feeds the dictionary. Measure % auto-recognised (target 90%+), time-to-first-dashboard (target <15 min).

Phase 5 — Depth
- Gmail direct connect (after CASA audit); Tally live connector (install, opt-in); PC agent for installed software and seat usage; AWS/Azure cost APIs; Google Workspace token audit for shadow apps; benchmarks ("factories your size pay ₹X for this"); renewal negotiation tips.

---

## 12. Tech choices (simple, cheap, known)
- Server: Python (FastAPI) + PostgreSQL; background jobs for parsing and monthly pulls.
- Dashboard: Next.js/React, mobile-friendly.
- Parsing: pandas for Excel/CSV; pdfplumber/camelot for PDF statements; OCR + LLM for invoice images (capped cost per file).
- Vendor recognition: rules + fuzzy first; LLM only for leftovers; global cache.
- Inbound email: Postmark or SendGrid Inbound Parse. WhatsApp: Meta Cloud API via AiSensy/Interakt/Gupshup. GST: Sandbox / Masters India GSP. Zoho: OAuth. Microsoft: Graph with admin consent.
- Hosting: India region; one small box serves the first few hundred companies.
- Security: read-only everywhere; encrypted storage; per-company isolation; audit log; data never leaves India.

---

## 13. Test set
52 input → expected-output cases are in `research/3-engine-logic-and-test-cases.md` (Part 5). Build these as automated tests before product code. Add 10 real bank statements (5 banks, Excel + PDF) and 5 Tally exports with resellers and vague narrations.

---

## 14. Open decisions (settle in design freeze)
- Product name.
- Pricing tiers and free-tier size.
- First channel: CAs, resellers, or direct to owners.
- v1 pipes: is GST (Phase 3) in the first release or right after?
- WhatsApp provider; GSP provider.
- Whether the Outlook admin-consent path is in v1 or forwarding-only.
