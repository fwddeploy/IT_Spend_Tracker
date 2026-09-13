Research is done. Here is the full design document.

---

# Subscription & IT-Licence Spend Engine — Design Notes for Indian Manufacturing MSMEs

Sources used are listed inline as links and again at the end. Where I could not verify a payee string from a public source I have marked it **(pattern, unverified)** so the developer knows to confirm against real statements.

---

## Part 1 — Catalogue of typical software / IT spend for an Indian manufacturing MSME

Legend for "How bought": **Direct-card** = paid online with a company/owner card; **Reseller** = Indian partner/reseller raises a GST invoice, paid by NEFT/RTGS/cheque/UPI; **Distributor** = Ingram/Redington/Savex-type distributor invoice via a local dealer. "Perp+AMC" = perpetual licence exists with a yearly maintenance/subscription fee.

### 1A. CAD / CAM / CAE

| Product | How bought in India | Cycle | Currency | Perp + AMC? | How payee appears |
|---|---|---|---|---|---|
| SOLIDWORKS (Dassault) | Almost always via an authorised Indian reseller (Cadspro, Beacon, Conceptia Konnect, EGS, CADD Centre etc.); annual "Subscription Service" for perpetual seats, or term licence billed yearly, +18% GST ([Cadspro pricing](https://www.cadsprotech.com/solidworks/pricing), [Beacon](https://beacon-india.com/solidworks-3dcad-software-reseller/)) | Yearly (term ₹1.8–3.2 lakh/yr/seat before GST); 3-year deals exist | INR | Yes: perpetual + yearly Subscription Service (~15–20% of licence) | Bank shows the **reseller** name: e.g. `NEFT-…-CADSPRO TECHNOLOGIES PVT LTD`, `BEACON INDIA`, `CONCEPTIA KONNECT`, `EGS COMPUTERS INDIA`. "DASSAULT" only appears if paying 3DEXPERIENCE cloud direct: `DASSAULT SYSTEMES` / `3DS*` (pattern, unverified) |
| AutoCAD / AutoCAD LT / Fusion / Inventor (Autodesk) | Both: (a) direct on autodesk.com/in with card, invoiced by Autodesk (GST charged), (b) Indian reseller (Arkance/Capricot, Tech Soft 3D partners, Autodesk Gold partners) ([Autodesk India promotions page](https://www.autodesk.com/in/promotions)) | Monthly / Yearly / 3-year (yearly most common). Flex tokens = prepaid usage | INR direct (USD if bought on .com) | No — subscription only since 2016; old perpetual+maintenance plans mostly retired | Direct: `AUTODESK`, `AUTODESK INC`, `AUTODESK*`, `ADSK*` (pattern, unverified). Reseller: `CAPRICOT TECHNOLOGIES`, `ARKANCE`, `CADD CENTRE` etc. |
| PTC Creo | Reseller only (Adroitec, EGS, Neilsoft partners, etc.) | Yearly / 3-year term | INR (reseller) | Historically perp + yearly maintenance; new sales are subscription | Reseller name only |
| Siemens NX / Solid Edge | Reseller (Siemens DI partners) | Yearly / 3-year; Solid Edge has monthly online | INR | Yes (perp + maintenance) for existing; new is subscription | Reseller name; `SIEMENS INDUSTRY SOFTWARE (INDIA) PVT LTD` for direct enterprise |
| Mastercam / Edgecam / hyperMILL / Delcam-PowerMill (Autodesk) | Reseller | Perpetual + yearly maintenance | INR | Yes, classic perp + AMC | Reseller name |
| ZWCAD / BricsCAD / DraftSight / GstarCAD (cheap AutoCAD alternatives) | Reseller or direct card | Yearly or perpetual+optional upgrade | INR/USD | Yes | `DASSAULT SYSTEMES` (DraftSight direct), reseller names |
| CNC post-processors / DNC software / small utilities | Local vendor, cheque/UPI | One-time or yearly | INR | Yes | Proprietor name or firm name |

### 1B. ERP / Accounting / Billing

| Product | How bought | Cycle | Currency | Perp + AMC? | Payee strings |
|---|---|---|---|---|---|
| TallyPrime (Silver ₹22,500, Gold ₹67,500) + TSS renewal (Silver ₹4,500, Gold ₹13,500 + 18% GST) ([Mark IT guide](https://www.markitsolutions.in/blogs/tally-renewal-charges-2026-guide)) | Tally partner (most common; GST invoice), in-product TallyShop (card/netbanking/UPI), or tallysolutions.com | Licence one-time; **TSS yearly** (renewal ≈20% of licence) | INR | **Yes — classic case**: perpetual licence + yearly TSS | Direct: `TALLY SOLUTIONS PVT LTD`, `TALLYSOLUTIONS`, `UPI/…/TALLY SOLUTIONS`; via partner: partner firm name (`XYZ INFOTECH`, `ABC TALLY SOLUTIONS`) — hundreds of small partner names |
| Tally on Cloud / Tally rental (third parties) | Cloud partner | Monthly / yearly | INR | No | Partner name (`TALLYATCLOUD`, `TALLYONCLOUD`…) |
| Busy Accounting | Busy partner or busy.in direct | Perpetual + yearly BLS (Busy Licence Service) OR subscription | INR | Yes | `BUSY INFOTECH PVT LTD`, partner names |
| Marg ERP | Partner | Perpetual + yearly AMC/upgrade | INR | Yes | `MARG ERP LTD`, `MARG COMPUSOFT` (old name), partner |
| SAP Business One | SAP partner (Uneecops, Cognitive, etc.) | Licence one-time + **yearly maintenance (~17–22%)**; cloud version monthly/yearly | INR | Yes | Partner name only |
| Zoho Books / Zoho One / Zoho CRM / Zoho Inventory | Direct card/UPI/netbanking (zoho.com/in, GST invoice from Zoho Corp Pvt Ltd, Chennai) or Zoho partner | Monthly / Yearly | INR | No | `ZOHO CORPORATION PVT LTD`, `ZOHO*`, `ZOHOCORP`, `ZOHO CORP`; via Razorpay/PayU sometimes |
| Odoo | Odoo India partner (implementation + yearly Odoo Enterprise) or odoo.com direct | Yearly (monthly available) | INR (partner) / USD or INR (direct) | No | `ODOO SA`, `ODOO INDIA`, partner names |
| ERPNext (Frappe) | frappecloud.com direct or partner | Monthly / yearly | INR/USD | No | `FRAPPE TECHNOLOGIES PVT LTD` |
| Local/custom ERP (many regional vendors: e.g. "Udyog", "Focus", "ProMan", "eResource") | Vendor direct, cheque/NEFT | Licence + yearly AMC; sometimes monthly support retainer | INR | Yes | Vendor firm name |
| Payment/e-way/e-invoice utilities (ClearTax, IRIS, Masters India, GSTZen) | Direct or CA-recommended | Yearly | INR | No | `DEFMACRO SOFTWARE PVT LTD` (= ClearTax legal name), `CLEARTAX`, `IRIS BUSINESS SERVICES` |

### 1C. Office / Email / Productivity

| Product | How bought | Cycle | Currency | Payee strings |
|---|---|---|---|---|
| Microsoft 365 Business Basic/Standard | Direct (admin center, card, invoice from Microsoft Regional Sales Pte Ltd with Indian GST) OR CSP reseller (Redington, Ingram-backed partners, local MSP) | Monthly or Yearly (annual commitment, monthly billing common) | INR | Direct card: `MSFT * E0…`, `MSFT*MICROSOFT 365`, `MICROSOFT*365`, `MICROSOFT*OFFICE 365`, `MICROSOFT*M365`, `MSBILL.INFO`, `MICROSOFT SERVICES`, `MICROSOFT*365 REDMOND WA` ([source](https://yourbankstatementconverter.com/blog/what-does-microsoft-365-show-up-as-on-bank-statement/), [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/543359/unknown-msft-billing-being-charged-to-my-credit-ca)). India bank statements often render as `POS 4XXXXX MSFT * E01000XXXXX` (HDFC style) or `VIN/MSFT*E0100…` (ICICI style). Reseller: partner name |
| Google Workspace | Direct (card/netbanking, invoiced by Google Cloud India Pvt Ltd in INR with GST) or Google partner (many small "Google Workspace reseller" MSPs) | Monthly (flexible plan) or Yearly | INR | `GOOGLE *Workspace_{domain}`, legacy `GOOGLE *GSUITE_{domain}`, `GOOGLE *SERVICES`, `GOOGLE *CLOUD_{BAID}` for GCP, `GOOGLE *Domains` (legacy). Google's rule: every descriptor starts with `GOOGLE *` ([Google payments help](https://support.google.com/paymentscenter/answer/9003663?hl=en-IN)). Some Indian banks print `GOOGLE INDIA DIGITAL SERVICES` for UPI/netbanking (pattern, unverified) |
| Zoho Mail / Zoho Workplace | Direct | Monthly/yearly | INR | `ZOHO CORPORATION`, `ZOHO*MAIL` |
| Windows / Office perpetual (Office Home & Business, Windows Pro) | Distributor/dealer with hardware, or Amazon/Flipkart | One-time | INR | Dealer name, `AMAZON`, `FLIPKART` |
| Rediffmail Pro / other cheap business email | Direct | Yearly | INR | `REDIFF.COM INDIA` |

### 1D. Security / Endpoint

| Product | How bought | Cycle | Perp+AMC | Payee strings |
|---|---|---|---|---|
| Quick Heal / Seqrite Endpoint Security (EPS) | Almost always through a dealer/reseller; 1-year or 3-year keys per user (₹500–1,200/user/yr street price) ([Cloudfy pricing guide](https://www.cloudfysystems.com/blog/seqrite-endpoint-pricing-india-2026), [IndiaMART listings](https://www.indiamart.com/proddetail/seqrite-endpoint-security-for-total-25-user-for-1-year-19220704291.html)) | Yearly / 3-yearly | No (it's a term key) | Dealer name; direct: `QUICK HEAL TECHNOLOGIES LTD`, `SEQRITE` |
| Kaspersky / ESET / Bitdefender / Sophos / Trend Micro / McAfee | Dealer/distributor (Sophos always via partner) | Yearly / 3-yearly | No | Dealer; direct card: `KASPERSKY LAB`, `ESET`, `BITDEFENDER`, `SOPHOS`, `NORTONLIFELOCK` |
| Firewall subscription (Sophos XG, Fortinet, SonicWall licences) | Partner | Yearly / 3-yearly | Hardware one-time + yearly licence | Partner name (mixed with hardware on same bill) |
| Backup (Acronis, Veeam, Druva) | Partner or direct | Yearly | No | `ACRONIS`, partner |

### 1E. Cloud / Hosting / Domain / SSL

| Product | How bought | Cycle | Currency | Payee strings |
|---|---|---|---|---|
| AWS (Indian account = Amazon Internet Services Pvt Ltd, AISPL, INR invoice with GST) ([AWS India accounts](https://docs.aws.amazon.com/accounts/latest/reference/managing-accounts-india.html)) | Direct card / netbanking (AISPL accepts these) | **Monthly, usage-based** | INR (AISPL) or USD (aws.amazon.com global) | `AMAZON WEB SERVICES`, `AMAZON MKTPLACE PMTS AMAZON.COM` (Marketplace) ([AWS re:Post](https://repost.aws/knowledge-center/credit-card-charge-aws)); India: `AMAZON INTERNET SERVICES`, `AISPL`, `AWS EMEA` (pattern, unverified) |
| Microsoft Azure | Direct or CSP partner | Monthly usage | INR | `MSFT*AZURE`, `MICROSOFT*AZURE`, partner |
| Google Cloud | Direct | Monthly usage | INR | `GOOGLE *CLOUD_{BAID}` |
| DigitalOcean / Linode / Vultr / Hetzner | Direct card | Monthly usage | USD | `DIGITALOCEAN.COM`, `LINODE`, `VULTR`, `HETZNER` |
| GoDaddy (domain/hosting/email/SSL) | Direct card/UPI (GoDaddy India, INR with GST) | Yearly / 2–3-yearly (domains 1–10 yrs); hosting often monthly | INR | `GODADDY.COM`, `GODADDY`, `DNH*GODADDY.COM`, `GODADDY.COM LLC`, `GODADDY INDIA WEB SERVICES` |
| Hostinger / Bluehost / HostGator India / BigRock | Direct | Yearly / multi-year (2–4 yr promos!) | INR | `HOSTINGER`, `HOSTINGER INTERNATIONAL`, `BIGROCK`, `ENDURANCE INTERNATIONAL` (old Bluehost/HostGator India parent), `NEWFOLD` |
| Namecheap / Cloudflare | Direct | Yearly / monthly | USD | `NAMECHEAP`, `CLOUDFLARE` |
| SSL certificates | With hosting vendor or SSL reseller | Yearly | INR/USD | Same as hosting vendor; `SSLS.COM`, `SECTIGO`, `DIGICERT` |
| Website AMC (local web agency) | Local agency, NEFT/cheque | Yearly, sometimes quarterly | INR | Agency firm name |

### 1F. Communication / Telephony

| Product | How bought | Cycle | Payee strings |
|---|---|---|---|
| Zoom | Direct card (Zoom charges Indian GST) | Monthly/yearly | `ZOOM.US`, `ZOOM VIDEO COMMUNICATIONS`, `ZOOM.US 888-799-9666` |
| Microsoft Teams | Part of M365 | — | As M365 |
| WhatsApp Business API (via BSPs: Interakt, WATI, AiSensy, Gupshup, Twilio, Infobip; direct Meta billing possible) | BSP direct, card/prepaid wallet top-up | Monthly plan + **usage-based conversation charges**; prepaid recharges irregular | `INTERAKT`, `HAPTIK`, `WATI`, `AISENSY`, `GUPSHUP`, `TWILIO`, `META PLATFORMS` / `FACEBK` (direct Meta) |
| Exotel / Knowlarity / MyOperator / Ozonetel (cloud telephony, IVR) | Direct; monthly plan + call usage; often prepaid credits | Monthly / yearly / prepaid | `EXOTEL TECHCOM PVT LTD`, `KNOWLARITY COMMUNICATIONS`, `MYOPERATOR` (VoiceTree Technologies), `OZONETEL` |
| SMS gateways (MSG91, Textlocal, Kaleyra, Gupshup, Fast2SMS, Value First) | Direct; **prepaid credit packs** | Irregular top-ups | `MSG91`, `WALKOVER WEB SOLUTIONS` (= MSG91 legal name), `TEXTLOCAL`, `IMIMOBILE`, `KALEYRA`, `FAST2SMS` |
| Broadband / leased line / SIM (Airtel, Jio, Tata, BSNL, local ISP) | Postpaid monthly bill | Monthly | `BHARTI AIRTEL`, `AIRTEL`, `JIO`, `RELIANCE JIO INFOCOMM`, `TATA COMMUNICATIONS`, `BSNL`, `HATHWAY`, `ACT FIBERNET`, local ISP names |
| Slack / Notion / Trello / Jira / Canva Teams | Direct | Monthly/yearly | `SLACK`, `SLACK TECHNOLOGIES`, `NOTION LABS`, `ATLASSIAN`, `CANVA*`, `CANVA PTY LTD` |

### 1G. HR / Payroll / Attendance

| Product | How bought | Cycle | Payee strings |
|---|---|---|---|
| GreytHR | Direct (per-employee/month, billed monthly or yearly) | Monthly / yearly | `GREYTIP SOFTWARE PVT LTD`, `GREYTHR` |
| Keka | Direct | Monthly/yearly | `KEKA TECHNOLOGIES`, `KEKA HR` |
| Zoho People / Zoho Payroll | Direct | Monthly/yearly | `ZOHO CORPORATION` |
| Biometric attendance (ESSL, Matrix, ZKTeco) + cloud AMC | Dealer; hardware one-time + yearly cloud/AMC | Yearly | Dealer name, `ESSL SECURITY` |
| Kredily / sumHR / Pocket HRMS / factoHR | Direct | Monthly/yearly | Vendor names |

### 1H. Design / Documentation

| Product | How bought | Cycle | Payee strings |
|---|---|---|---|
| Adobe Creative Cloud / Acrobat Pro | Direct card (invoiced by Adobe Systems Software Ireland Ltd; GST charged for India) or reseller (for VIP/teams) | Monthly (annual plan billed monthly) / yearly | `ADOBE SYSTEMS SOFTWARE IRELAND LTD`, `ADOBE *CREATIVE`, `ADOBE CREATIVE*`, `ADOBE ACROBAT*`, `ADOBE PHOTOSHP*`, `ADOBE STOCK*`, `ADOBE INC`, `ADOBE.COM`, `ADOBE SYSTEMS` ([source](https://yourbankstatementconverter.com/blog/what-does-adobe-show-up-as-on-bank-statement/), [Adobe community](https://community.adobe.com/t5/account-payment-plan-discussions/adobe-systems-software-ireland-ltd-charge/m-p/14834700)) |
| Canva Pro/Teams | Direct card | Monthly/yearly | `CANVA*`, `CANVA PTY LTD`, `CANVA* I0…` |
| CorelDRAW | Reseller or direct | Yearly / perpetual | `COREL`, `ALLUDO`, reseller |

### 1I. Compliance / Tax / Finance

| Product | How bought | Cycle | Payee strings |
|---|---|---|---|
| ClearTax GST / e-invoicing / TDS | Direct (or via CA) | Yearly | `DEFMACRO SOFTWARE`, `CLEARTAX` |
| GST filing via CA (service, not software) | Cheque/NEFT | Quarterly/yearly | CA firm name |
| Digital signature (DSC) renewal — eMudhra, Sify, Capricorn | Local DSC agent | 1/2/3-yearly | Agent name, `EMUDHRA`, `SIFY`, `CAPRICORN IDENTITY` |
| TDS software (Saral, Winman, CompuTax), Tally add-ons (TDLs) | Direct/partner | Yearly | Vendor names |
| MCA / GST / IEC government fees | Netbanking (BharatKosh, GST portal) | Irregular | `MCA21`, `BHARATKOSH`, `GST` — **not subscriptions; exclude** |

### 1J. Hardware AMC, IT support, printing

| Item | How bought | Cycle | Payee strings |
|---|---|---|---|
| IT support AMC (local MSP: "XYZ Computers") | Cheque/NEFT; quarterly or yearly; sometimes monthly retainer | Quarterly / yearly | Local firm name — same firm often also sells laptops, toner, antivirus, M365 |
| Printer/copier AMC or per-page rental (Canon, Ricoh, Konica dealers) | Monthly rental + per-page usage | Monthly variable | Dealer name |
| CCTV/UPS/server AMC | Local vendor | Yearly | Vendor name |
| Hardware warranty extensions (Dell ProSupport, HP Care Pack) | Bought with hardware | 3-yearly, one-time | Dealer name |

### 1K. Payment-gateway / wallet pass-through names (mask the real vendor)

| Gateway | Typical strings |
|---|---|
| Razorpay | `RAZORPAY`, `RAZORPAY SOFTWARE PVT LTD`, `RAZ*<merchant>`, `RAZORPAY*<merchant>`; UPI: `UPI/…/razorpay.<merchant>@…` — the VPA usually contains the merchant slug |
| PayU | `PAYU*<merchant>`, `PAYUMONEY`, `PAYU PAYMENTS PVT LTD` |
| CCAvenue | `CCAVENUE*<merchant>`, `AVENUES INDIA PVT LTD` |
| Cashfree / Instamojo / Paytm / PhonePe / BillDesk | `CASHFREE`, `INSTAMOJO`, `PAYTM*`, `PHONEPE`, `BILLDESK` |
| Stripe | `STRIPE*<merchant>` or the merchant's own descriptor |
| PayPal | `PAYPAL *<MERCHANT>`, `PAYPAL *<merchant> 4029357733` |
| Apple / Google app billing | `APPLE.COM/BILL`, `GOOGLE *<Developer>` |

Bank-specific row formats you will meet (India):
- HDFC card: `POS 4XXXXXXX MSFT * E0100 ...`, `POS ... ADOBE SYSTEMS SOFTWARE` ; forex: separate line `DCC MARKUP` / `FOREIGN CURRENCY MARKUP`.
- ICICI: `VIN/GOOGLE*GSUITE/20240105/…`, `IIN/…`, `BIL/ONL/…` (netbanking bill pay).
- SBI/Axis/Kotak: `POS 12XX ZOOM.US`, `ECOM PUR/…`.
- NEFT/RTGS/IMPS: `NEFT-<UTR>-<BENEFICIARY NAME>-<remarks>`, `RTGS/…`, `IMPS/…/<name>/…`.
- UPI: `UPI/<txn id>/<payee name or VPA>/<remark>/<bank>` — payee VPA like `tallysolutions.rzp@hdfcbank`.
- Standing instructions/NACH: `SI <merchant>`, `ACH D- <mandate name>` (e-mandates for M365, Zoho, Airtel etc.).

---

## Part 2 — Tricky situations and the rule for each

Tax/regulatory facts used below (verify with the client's CA yearly):
- **GST on domestic software/SaaS** = 18% ([Tax Garden SAC guide](https://taxgarden.in/blog/gst-on-it-software-services-india-rates-sac-codes-2026)). Invoice "taxable value" ≠ bank debit; bank debit = taxable + 18% (minus TDS, if any).
- **Foreign vendor with no Indian GST registration** (OpenAI, Notion, Vercel, DigitalOcean, Namecheap…): the Indian business pays **18% IGST under reverse charge (RCM)** through the cash ledger, issues a self-invoice, and claims ITC; no threshold ([zero8.dev](https://zero8.dev/blog/rcm-on-import-of-services-cloud-saas-india), [IndiaFilings](https://www.indiafilings.com/gst/import-of-services-under-gst)). Bank debit = foreign amount only; the 18% appears as a separate GST cash-ledger payment, never on the vendor line.
- **Foreign vendor with Indian entity/GST registration** (AWS via AISPL, Google Cloud India, Microsoft, Adobe Ireland, Zoom for India): they charge 18% GST on the invoice → normal B2B; bank debit includes GST.
- **TDS Sec 194J**: threshold **₹50,000 per payee per FY from FY 2025-26** (was ₹30,000); **2% for fees for technical services, 10% for professional fees/royalty** ([Tax Garden](https://taxgarden.in/blog/tds-threshold-changes-fy-2025-26-budget-2025-new-limits-india), [TDSMan](https://blog.tdsman.com/2025/07/tds-under-section-194ja-194jb/)). Practice varies: many MSMEs deduct 2% on AMC/support/SaaS; **no TDS** on shrink-wrapped software bought from a reseller if the reseller gives a CBDT Notification 21/2012 declaration ([Busy guide](https://busy.in/tds/tds-on-software-purchase-in-india-a-complete-guide-for-businesses/), [Saral](https://saral.pro/blogs/tds-on-software-purchase/)).
- **Sec 195 (foreign vendor)**: after *Engineering Analysis Centre of Excellence v CIT* (SC, 2021), payment for use of off-the-shelf software is **not royalty**, so usually **no TDS** on foreign SaaS/licence if treaty benefit is available (TRC/Form 10F); some CAs still deduct conservatively ([Taxscan](https://www.taxscan.in/no-tds-applicable-on-indian-companies-for-amount-paid-to-use-foreign-software-supreme-court/103203), [Karnani & Co](https://www.karnanica.com/tds-on-purchase-of-software-from-outside-india/)). Card payments to foreign vendors practically never have TDS deducted (nobody can withhold from a card charge).
- Equalisation levy 2% was withdrawn 1 Aug 2024; the 6% levy on online ads was abolished from 1 Apr 2025 — no longer relevant to software (treat as out of scope; confirm with CA).

Now the situations. Each gives: **what you see → rule**.

### 2.1 Billing cycles

1. **Monthly** – gaps of 28–33 days. Rule: classify as MONTHLY if median gap is 27–34 days and ≥2 gaps agree.
2. **Quarterly** – gaps 85–97 days. Rule: QUARTERLY if median gap 84–98. Common for IT AMC and web AMC.
3. **Half-yearly** – gaps 175–190. Rule: HALF_YEARLY if median gap 170–195.
4. **Yearly** – gaps 350–380. Rule: YEARLY if median gap 340–395 (some vendors renew a few weeks early or late; Indian FY-aligned bills cluster around end-March/early-April).
5. **2-year / 3-year** – domains, Seqrite 3-yr keys, hosting promos, Autodesk 3-yr. Rule: if gap 700–760 → BIENNIAL; 1060–1130 → TRIENNIAL. With only one occurrence you cannot know; use vendor default (see 2.5) and mark cycle confidence LOW.
6. **Weekly / ad-hoc** – rare for software; treat weekly patterns as "not a subscription" unless the vendor is a known SaaS.
7. **Mixed within one vendor** (Zoho: monthly Books + yearly Mail). Rule: group by vendor **and product hint and amount band**, never by vendor alone (see Part 3).

### 2.2 History too short

8. **Single payment seen once**. Rule: create a *candidate* subscription, cycle = vendor's default cycle from the alias dictionary (e.g. TSS → yearly, GoDaddy domain → yearly, AWS → monthly). Confidence LOW. If the invoice email/Tally narration shows a period ("01-Apr-25 to 31-Mar-26", "1 year", "12 months", "annual") use that and raise confidence to MEDIUM. Ask the user only if the vendor is unknown and amount ≥ ₹5,000.
9. **Two payments** (Plaid calls this "early detection", <3 occurrences ([Plaid blog](https://plaid.com/blog/recurring-transactions/))). Rule: cycle = the one gap, snapped to the nearest standard cycle; confidence MEDIUM; show to user as "looks like … — confirm?".
10. **Three or more** → "mature" stream; auto-accept if score ≥ threshold (Part 3).

### 2.3 Licence models

11. **Perpetual licence + yearly AMC/TSS/Subscription Service** (Tally, SolidWorks, SAP B1, Busy, Marg). You see one big payment (₹22,500 / ₹2 lakh) then a much smaller yearly one (₹5,310 / ₹40,000). Rule: if the same vendor/product has one payment ≥3× the later repeating amount and it occurs first, tag the big one as **ONE_TIME_LICENCE** (capex, not a subscription) and build the subscription from the smaller repeating amounts. Show "Licence bought on <date>; maintenance ₹X/yr, next due <date>". If the maintenance stops, the licence still works (Tally) → status "AMC lapsed", not "cancelled".
12. **Term licence sold as "subscription"** (SolidWorks term, Autodesk) – nothing special; it is a yearly subscription. Rule: default YEARLY.
13. **Multi-year prepaid** (3-yr Seqrite, 2-yr domain). Rule: cycle = TRIENNIAL; monthly-equivalent = amount/36; next due = date + 3 years. If the invoice text says "3 years / 36 months", use it; else ask user once.

### 2.4 Variable amounts

14. **Usage-based (AWS, Azure, Exotel, printer rental, telecom)**. Amounts differ every month. Rule: amounts are allowed to vary; for vendors flagged `variable=true` in the dictionary, amount tolerance is ±60% around the trailing 3-month median, and the cycle is inferred from **dates only**. Show "≈ ₹X/month (avg of last 3)". Never flag a price change for these.
15. **Prepaid credits / top-ups (SMS, WhatsApp, Exotel wallet, Google Ads)**. Irregular dates, round amounts (₹5,000, ₹10,000). Rule: if gaps are irregular (CV of gaps > 0.5) and amounts are round numbers → type **PREPAID_CREDITS**, no next due date; compute monthly run-rate = total spend over last 6 months ÷ 6; show "Top-up expected roughly every N days".
16. **Seat count change** (M365 from 10 → 12 users: ₹1,450 → ₹1,740). Rule: amount jumps by a whole multiple of a plausible per-seat price and stays there → same stream, note "quantity changed on <date>"; do not split the stream. Implementation: new amount within ±100% and new value repeats at least once, or invoice shows quantity change.
17. **Price hike** (Adobe +10%, Google Workspace price rises). Rule: single step change ≤ +50% that persists → same stream, record "price changed from A to B on <date>", update expected amount to the latest amount (Plaid keeps both `average_amount` and `last_amount` for exactly this reason ([Plaid blog](https://plaid.com/blog/recurring-transactions/))). Predict future using **last amount**, not the average.
18. **Discount / promo first year then full price** (Hostinger ₹1,800 first year, ₹6,000 renewal). Rule: same as price change; if the second amount > 2× first and the vendor is flagged `intro_pricing=true`, warn the user that renewal is at full price.

### 2.5 Date irregularities

19. **Late payment / date drift** (yearly AMC paid 3 weeks late; monthly card charge slipping from 3rd to 5th). Rule: tolerance windows by cycle — monthly ±5 days, quarterly ±10, half-yearly ±15, yearly ±30, 3-yearly ±45. Drift within tolerance does not break the stream; the **anchor day** is re-computed as the median day-of-month (monthly) or median day-of-year (yearly) of the last 3 occurrences.
20. **Paid early** (renewed a month before expiry; Tally partners push early-renewal offers). Rule: an occurrence up to 45 days before the expected date (yearly) or 10 days (monthly) counts as the same cycle's payment; next due = **previous expected due + cycle**, not payment date + cycle, when the invoice shows a validity period. If no invoice, next due = payment date + cycle (conservative).
21. **Two months paid together** (one debit = 2× the monthly amount after a missed month). Rule: if a debit ≈ N × expected amount (N = 2 or 3, ±3%) and the previous N−1 expected dates were missed → treat as N catch-up payments; mark the stream current; do not create a new stream or flag a price hike.
22. **Partial payment** (₹30,000 of a ₹50,000 invoice, balance later). Rule: if two debits within 45 days to the same vendor sum (±2%) to a known invoice amount, or to the previous cycle's amount → merge into one occurrence. If no invoice is known, keep them as separate occurrences but flag "possible split payment" and ask once.
23. **Payment split across two bank lines** (RTGS limit, or two cards). Rule: same as 22; also match by identical narration/UTR reference prefix within the same day.
24. **Refund / reversal** (credit from the same vendor within 30 days of a debit, same amount). Rule: cancel the matching debit occurrence; if the refund amount equals the last charge and no further charge follows, status → CANCELLED (refunded). A partial refund → pro-rated seat reduction; keep the stream.
25. **Trial-to-paid** (₹0 or ₹1/₹2 authorisation charge, then full charge). Rule: ignore debits ≤ ₹5 and any zero-value invoice; but if a ₹1 auth is followed by a real charge from the same vendor, backdate the stream start to the auth date for "subscribed since".
26. **Cancelled subscription**. Rule: when an expected date + grace passes with no payment → OVERDUE; after 2 missed cycles (monthly) or 1 cycle + 60 days (yearly) → STOPPED. If a "cancellation" or "subscription ended" email exists → CANCELLED immediately. Show STOPPED subs in a separate list so the user can confirm "cancelled" vs "forgot to pay".

### 2.6 Vendor identity shifts

27. **Vendor switched from reseller to direct (or the reverse)** — e.g. M365 bought via "ABC Infotech" for 2 years, then via card `MSFT*`. Rule: streams are keyed by **product**, not payee. If a new payee maps (via dictionary) to the same product and the old payee's stream stops within one cycle of the new one starting, and the amount is within ±25% → merge: "Supplier changed from ABC Infotech to Microsoft direct".
28. **Same reseller, many products on one bill** (dealer bill: Seqrite 25 users + M365 10 users + Tally TSS). Rule: if line-item data exists (invoice email/Tally purchase register with items), create one stream per line item, each carrying the reseller as payee and the product from the item. If only the bank line exists, create one stream "ABC Infotech — bundle" and ask the user once to split it (offer detected product hints from the amount, e.g. ₹5,310 = TSS Silver).
29. **Reseller bill mixing hardware + software** (laptops ₹1.2 lakh + Windows licence ₹9,000 + AV ₹15,000). Rule: hardware line items (HSN 84xx/85xx, words "laptop, desktop, printer, RAM, SSD, cable, toner") are excluded from subscriptions; only lines with HSN 9973/9983/9984/998313-16 (SAC), words "licence, subscription, renewal, AMC, support, annual, cloud, user" become candidates. If only a bank line exists and the amount is unusually large for that reseller (>3× their median), treat as one-time and ask.
30. **Payment gateway hides the vendor** (`RAZORPAY SOFTWARE`, `PAYU*`, `CCAVENUE*`, `STRIPE*`, `PAYPAL *`). Rule: strip the gateway prefix and try to match the suffix (`RAZ*ZOHO`, `PAYPAL *GODADDY`). If nothing remains, look for a matching invoice email or Tally entry within ±3 days for the same amount; if found, use that vendor. If not, group by (gateway, amount) and ask the user once: "₹2,360 via Razorpay on the 5th every month — who is this?" Save the answer as an alias for `(gateway, amount-band, day-of-month)`.

### 2.7 Currency, tax, and withholding

31. **Foreign currency with changing INR amount**. USD 54.99 becomes ₹4,610 one month, ₹4,700 the next, plus a separate `FOREIGN CURRENCY MARKUP` line (1–3.5%) and its GST. Rule: (a) if the statement shows the original currency amount, group on the **foreign amount**; (b) otherwise allow ±8% amount tolerance for vendors flagged `currency=USD`; (c) fold the markup line (same day, description contains MARKUP/DCC/FX, amount ≤ 5% of the main debit) into the occurrence as `fees`. Report both "USD 54.99" and "₹4,700 incl. markup".
32. **Invoice amount vs bank debit with 18% GST**. Invoice ₹10,000 + ₹1,800 = ₹11,800 debit. Rule: when matching invoice to bank, test bank = invoice_total, bank = taxable × 1.18, bank = taxable (RCM case) — all ±₹2. Store `amount_taxable`, `gst`, `amount_paid` separately; reports show gross cash out and optionally "net of ITC".
33. **RCM on foreign SaaS**. Bank debit to `NOTION LABS` = ₹850; a separate GST cash-ledger challan later covers ₹153 IGST. Rule: foreign vendor + no GST on invoice → tag `gst_mode=RCM`; compute notional 18% and show it as "GST payable by you under RCM (ITC claimable)". Do not try to match the challan to the vendor.
34. **TDS deduction making the bank debit smaller** — invoice ₹1,18,000 (₹1,00,000 + GST); TDS 2% on ₹1,00,000 = ₹2,000; bank debit ₹1,16,000. Rule: when a bank debit is short of the invoice by exactly 1%, 2%, 10% (or 20% if no PAN) **of the taxable value** (±₹5), match it and record `tds_rate`, `tds_amount`. Recurrence grouping should use the **invoice/gross amount** when known, so that a vendor who crosses the ₹50,000/FY threshold mid-year (TDS starts being deducted from, say, the 6th month) does not look like a price cut. Also allow bank = taxable×1.18 − taxable×tds where tds ∈ {0.01, 0.02, 0.10, 0.20}.
35. **TDS paid on the vendor's behalf later** — the ₹2,000 goes to government via a TDS challan (`TIN NSDL`, `OLTAS`, `TDS CHALLAN`). Rule: exclude government challans from vendor matching (pattern list: `CBDT`, `OLTAS`, `GST PMT`, `BHARATKOSH`, `MCA21`).

### 2.8 Who paid, and how

36. **Owner paid from a personal card / UPI** (Adobe on the MD's HDFC card; reimbursed later or booked as "Director's current account"). Rule: allow multiple accounts, including personal ones, tagged `owner_personal`. Streams match across accounts. If a subscription is seen on a personal account and there is a Tally journal "Adobe – paid by director", link them. Show in the report as "Paid from: MD personal card" and warn "not in company books" if no Tally entry exists.
37. **Cash / cheque to a local vendor** (cheque `CHQ 000123` with no name; cash entry only in Tally). Rule: bank line for cheque has no payee → resolve via Tally (cheque number match) or ask once. Cash entries come only from Tally: treat Tally as the source of truth for those occurrences.
38. **Duplicate detection across Tally, bank and email**. Rule: an *occurrence* is unique by (vendor_id, invoice_number) if the invoice number is known; else by (vendor_id, amount ±2%, date window). Windows: email ↔ bank ±15 days; Tally ↔ bank ±60 days (accounting lags); email ↔ Tally ±60 days. When merged, keep: **date = bank date** (cash truth), **amount = bank**, **description/product/period = invoice**, **ledger/category = Tally**. Never count the same invoice twice in spend.
39. **Accounting entries lag by weeks** (Tally entry dated 30-Apr for an AWS bill paid 5-Apr). Rule: Tally date is the *booking* date; when it is within 60 days after the bank date and amounts match, merge. Recurrence and due dates are always computed from bank dates.
40. **Multiple companies / branches under one owner** (two GSTINs, one M365 tenant paid from company A; Tally licences in both). Rule: every source row carries `entity_id`. Streams are per entity by default. If the same vendor stream appears in two entities with the same product, flag "possible cross-charged shared licence"; allow the user to mark a stream as "shared, paid by A, used by A+B" so that per-entity reports allocate it by seat %.
41. **Financial-year framing (April–March)**. Rule: yearly subs are tagged with FY of *service period* (from invoice period if known, else FY of payment date). Reports offer both calendar and FY views; renewals falling in March/April are the busiest and are highlighted as "FY-end renewals".
42. **Auto-charge vs manual pay**. Rule: source hint decides — card/standing-instruction/NACH (`SI`, `ACH D-`, `ECOM`, `POS`) → `auto_renew=true`; NEFT/RTGS/cheque/UPI/cash → `manual=true`. For manual ones, reminders are due **before** the date (14 days for yearly, 5 for monthly); for auto ones, the reminder is "will be charged on…" and the risk is card expiry, not forgetting.
43. **Same amount, two different vendors** (₹2,360 to Zoho and ₹2,360 to Canva). Rule: amount alone never groups; vendor is always part of the key.
44. **Bank "charges" and interest lines mixed in** (`FOREX MARKUP`, `SMS ALERT CHG`, `CONSOLIDATED CHARGES`). Rule: bank fee patterns are excluded from vendor streams; only the forex markup tied to a foreign subscription is folded in (2.31).
45. **Gateway settlement / vendor payout lines** (if the MSME itself sells online, it receives `RAZORPAY` credits). Rule: only debits are candidates; credits are considered only as refunds (2.24).
46. **Vendor's legal name ≠ brand** (ClearTax = Defmacro Software; MSG91 = Walkover Web Solutions; GreytHR = Greytip Software; Knowlarity; MyOperator = VoiceTree). Rule: alias dictionary maps legal names to brand (Part 4).
47. **Same-day duplicate debit then reversal** (card retried). Rule: two identical debits same day + a credit within 7 days → keep one occurrence.
48. **Rounded UPI amount vs exact invoice** (UPI ₹5,300 for a ₹5,310 bill — cash discount). Rule: match tolerance ±2% or ₹50, whichever is larger, when matching to invoice.

---

## Part 3 — Recurrence-detection algorithm

What was borrowed: Plaid groups on *description + amount + cadence*, needs **3 occurrences for "mature"** (fewer = "early detection"), keeps `average_amount` and `last_amount`, exposes `is_active` and `predicted_next_date`, excludes habitual purchases like groceries, and recommends ≥180 days of history ([Plaid recurring blog](https://plaid.com/blog/recurring-transactions/), [Plaid docs](https://plaid.com/docs/api/products/transactions/)). Actual Budget's `find-schedules.ts` groups by payee, tests weekly/bi-weekly/monthly(day 1–28)/last-day/nth-weekday patterns, allows **±2 days** date slop, requires the last **3** pattern dates to each have a matching transaction, and uses an amount-dependent tolerance (`getApproxNumberThreshold`) ([source](https://raw.githubusercontent.com/actualbudget/actual/master/packages/loot-core/src/server/schedules/find-schedules.ts)). Subaio (bank-side subscription detection) uses clustering on merchant + amount + frequency and improves with user flags ([Subaio](https://subaio.com/subaio-explained/how-does-subaio-detect-recurring-payments)). Firefly III does not auto-detect; it models user-declared recurrences with repeat type, skip and end-date, which is a good model for what we store after detection ([Firefly III docs](https://docs.firefly-iii.org/how-to/firefly-iii/finances/recurring/)). Our differences: Indian cycles are mostly **yearly/quarterly**, not weekly; amounts vary because of GST/TDS/forex; three sources must be de-duplicated first.

### Step 0 — Normalise every row into one shape
`{entity_id, source (bank|card|email|tally), account_id, date, amount_paid, amount_taxable?, gst?, tds?, currency, fx_amount?, raw_description, payee_clean, vendor_id?, product_hint?, invoice_no?, period_from?, period_to?, quantity?, direction (debit|credit), payment_mode (card|upi|neft|rtgs|cheque|cash|si|nach)}`
Cleaning `payee_clean`: uppercase; strip bank prefixes (`POS`, `VIN/`, `IIN/`, `UPI/`, `NEFT-`, `IMPS/`), transaction ids, dates, card fragments, city/country suffixes (`DUBLIN`, `SINGAPORE`, `REDMOND WA`), `PVT LTD/PRIVATE LIMITED/LLP/LTD`; strip gateway prefixes but keep the remainder; collapse whitespace.

### Step 1 — Vendor resolution (Part 4) → `vendor_id`, `product_hint`, vendor flags (`default_cycle`, `variable`, `currency`, `is_gateway`, `is_reseller`, `is_bank_fee`, `exclude`).

### Step 2 — Cross-source de-duplication → *occurrences* (rules 2.38–2.39). Output: one occurrence per real payment with the best fields from each source and `sources[]`.

### Step 3 — Grouping key
`(entity_id, vendor_id, product_hint or "*", amount_band, currency)`
- `amount_band`: for fixed vendors, occurrences whose gross/invoice amount is within ±10% of each other (after removing TDS and folding markup) go in one band; for `variable` vendors, one band per vendor/product regardless of amount.
- Then a **merge pass**: bands for the same vendor/product whose date ranges do not overlap and whose amounts differ by a step change (2.16/2.17) are merged into one stream with an amount-history.
- Streams with `product_hint="*"` for a reseller are "bundle" streams (2.28).

### Step 4 — Gap analysis per stream
1. Sort occurrences by date; compute gaps in days.
2. Fold catch-ups (2.21) and splits (2.22/2.23) first.
3. Take the **median gap** (robust to one late payment). Snap to the nearest cycle:

| Cycle | Nominal days | Accept median in | Per-gap tolerance |
|---|---|---|---|
| WEEKLY | 7 | 6–8 | ±1 |
| MONTHLY | 30.4 | 27–34 | ±5 |
| QUARTERLY | 91 | 84–98 | ±10 |
| HALF_YEARLY | 182 | 170–195 | ±15 |
| YEARLY | 365 | 340–395 | ±30 |
| BIENNIAL | 730 | 700–760 | ±40 |
| TRIENNIAL | 1096 | 1060–1130 | ±45 |

4. Count `on_cycle_gaps` = gaps within per-gap tolerance of the chosen cycle (also accept gaps that are 2× or 3× nominal — those are *missed* cycles, counted separately as `missed`).
5. If no cycle fits (gap CV > 0.5 and no snap) → `IRREGULAR` (prepaid credits / ad-hoc).

### Step 5 — Confidence score (0–100)
- +30 if occurrences ≥ 3 (mature); +15 if 2; +0 if 1.
- +25 × (on_cycle_gaps / total_gaps).
- +15 if amount stability good (fixed vendor: all within ±3%; variable vendor: dates fit).
- +15 if vendor is in the dictionary as a known subscription vendor and detected cycle = its default cycle (+8 if in dictionary but cycle differs).
- +10 if an invoice/Tally line says "renewal / subscription / AMC / annual / period from–to".
- +5 if payment mode is SI/NACH/card ecom (auto-renew hint).
- −20 if last occurrence is older than 2 cycles (probably stopped).
- −10 if the payee is a gateway string that was resolved only by amount/date.

Decision: **≥ 75 auto-accept** (show as confirmed); **45–74 show as "likely, confirm?"** (one tap); **< 45 keep as candidate**, listed under "Unclassified vendor payments", ask only if the yearly value ≥ ₹5,000 or the vendor is flagged software-ish by the LLM. Every user answer feeds the alias dictionary and raises that stream to 100 (`is_user_modified`, as Plaid does).

### Step 6 — Expected amount
- Fixed: `expected = last_amount` (not average) — after a price hike or seat change the last one is the right predictor. Keep `average_amount` for display and for spotting changes.
- Variable: `expected = median of last 3`, show a range (min–max of last 6).
- Store gross (with GST) for "cash out", and taxable for "net of ITC".

### Step 7 — Next due date
1. If the latest invoice has `period_to` → `next_due = period_to + 1 day` (most reliable; Tally/TSS, SolidWorks, domain invoices all state validity).
2. Else `next_due = last_paid_date + cycle`, adjusted to the **anchor**: monthly → median day-of-month of last 3 (clamped to month length); yearly → same day/month as the median of prior occurrences.
3. If a catch-up payment was made (2.21), `next_due = last expected date + cycle`.
4. For prepaid/irregular → no due date; show "typical gap N days, last top-up X days ago".
5. Weekends/holidays: no shift for auto-charges; for manual (NEFT/cheque), if next_due falls on a Sunday, show the prior Friday as "pay by".

### Step 8 — Status rules
- `ACTIVE`: last payment within one cycle + grace.
- `DUE_SOON`: next_due within reminder window (monthly 5 d, quarterly 10 d, yearly 30 d, 3-yearly 45 d).
- `OVERDUE` (manual) / `CHARGE MISSED` (auto): today > next_due + grace (grace = monthly 7 d, quarterly 15 d, half-yearly 20 d, yearly 30 d).
- `STOPPED`: today > next_due + 1 full extra cycle (monthly: 2 missed months; yearly: 12 months past due + 30 d) or a cancellation email/refund seen → `CANCELLED`.
- `AMC_LAPSED`: variant of STOPPED for perpetual+AMC products (software still works).
- `ONE_TIME`: licence purchases, hardware — never get due dates.
- Manual override always wins (Plaid `is_user_modified`; Firefly's "repeat until" for a known end date).

### Step 9 — "Cash going out this month" vs "monthly-equivalent"
- **Cash out (month M)** = Σ expected amounts of all streams whose `next_due` (and any subsequent due dates) fall in M, + median run-rate for variable/prepaid streams, + already-paid occurrences dated in M. Shown as gross (incl. GST). Also list "known one-time renewals" (3-yearly etc.) landing in M.
- **Monthly-equivalent (MEQ)** = Σ over active streams of `expected_gross / months_in_cycle` (monthly 1, quarterly 3, half-yearly 6, yearly 12, biennial 24, triennial 36; variable → trailing-3 median). This is the "true burn rate" that does not spike in March/April.
- **Annualised** = MEQ × 12. Provide per-category and per-entity splits, and a "next 12 months calendar" listing every due date so FY-end clustering is visible.
- Both views separate "committed" (auto-renew or contract) from "discretionary" (manual pay).

---

## Part 4 — Vendor recognition

Layered pipeline, cheapest first; every layer records how it matched so confidence can be scored.

**Layer 1 — Deterministic clean-up + alias dictionary (exact/prefix/regex).**
Dictionary row: `{alias_pattern (regex or prefix), vendor_id, product_hint, category, default_cycle, variable, currency, is_gateway, is_reseller, entity_type (foreign_no_gst | foreign_gst_registered | domestic), tds_typical (0|2|10), notes}`. Examples: `^GOOGLE \*?(GSUITE|WORKSPACE)` → Google Workspace, office, MONTHLY|YEARLY, INR; `^(MSFT|MICROSOFT)\s?\*?\s?E0` → M365; `^ADOBE` → Adobe CC; `AMAZON (WEB|INTERNET) SERVICES|AISPL` → AWS, variable; `DEFMACRO` → ClearTax; `WALKOVER` → MSG91, prepaid; `TALLY SOLUTIONS` → Tally TSS/licence; `RAZORPAY|RAZ\*|PAYU|CCAVENUE|PAYPAL \*|STRIPE\*` → gateway (strip and retry on remainder). Payment-mode-specific: UPI VPAs (`.rzp@`, `@paytm`) carry merchant slugs — parse the slug.

**Layer 2 — Fuzzy match** against dictionary names and against *previously resolved payees of this customer* (token-set ratio / Jaro-Winkler ≥ 0.88 after cleaning; give extra weight to rare tokens; ignore tokens like INFOTECH, TECHNOLOGIES, SOLUTIONS, SYSTEMS, INDIA, PVT). Also match by **amount fingerprint**: if an unknown payee's amount equals a well-known list price (₹5,310 TSS Silver; ₹15,930 TSS Gold; M365 per-seat multiples ₹145/₹1,450…) propose that product with a "guess" flag.

**Layer 3 — Cross-source lookup**: unknown bank payee → search invoice emails / Tally purchase register for the same amount within ±15/±60 days; adopt that vendor/product. This is the main way to see through gateways and cheques.

**Layer 4 — LLM fallback** (only for still-unknown payees with ≥ ₹2,000 total or ≥ 2 occurrences): prompt with cleaned payee, amounts, dates, payment mode, any email subject lines; ask for `{vendor_brand, legal_name?, is_software_or_it (yes/no/unsure), product, category, likely_cycle, is_reseller, confidence}`. Accept only if confidence ≥ 0.8 and category is IT-ish; otherwise route to the user. Cache results globally (same string for all customers) with a review flag.

**Layer 5 — Ask the user once** with a pre-filled suggestion: "₹11,800 to 'SHREE INFOTECH' every April — is this (a) Tally TSS, (b) antivirus renewal, (c) IT AMC, (d) hardware, (e) other?" The answer is saved as a **customer-scoped alias** (`payee → vendor/product`) and, if the same string appears in many customers, promoted to the global dictionary after review.

**Seeding the dictionary**: (1) the Part-1 catalogue strings; (2) GSTIN/company-name lists of major vendors' Indian entities (MCA name search) to get legal names; (3) public charge-identifier lists ([Google](https://support.google.com/paymentscenter/answer/9003663?hl=en-IN), [AWS](https://repost.aws/knowledge-center/credit-card-charge-aws), [Microsoft](https://learn.microsoft.com/en-us/answers/questions/543359/unknown-msft-billing-being-charged-to-my-credit-ca), Adobe/M365 descriptor lists cited above); (4) Tally/SolidWorks/Autodesk/Seqrite **partner directories** scraped into a `reseller` list with `sells: [tally, seqrite, m365…]` so a reseller name immediately suggests a product menu; (5) UPI handle patterns for major merchants; (6) the first 50 real customers' confirmed answers.

**Reseller handling**: a reseller row resolves to `vendor_id = reseller`, `product = unknown`. Products are attached from invoice line items (Layer 3), amount fingerprints (Layer 2), or the user (Layer 5). Streams are keyed on product so that "Tally TSS via Shree Infotech" and "Tally TSS via Tally direct" merge (2.27). Reports can show both views: by product (what you use) and by payee (who you pay).

---

## Part 5 — Test cases (input pattern → expected output)

Amounts in ₹ unless stated. "Occ" = occurrences. Assume today = 12-Sep-2026 unless stated.

| # | Input pattern | Expected engine output |
|---|---|---|
| 1 | Card: `MSFT * E0100ABCD` ₹1,450 on 3-Jan, 3-Feb, 4-Mar, 3-Apr | Vendor Microsoft 365; MONTHLY; expected ₹1,450; next due 3-May-anchored (day 3); status ACTIVE; confidence ≥ 80; auto_renew |
| 2 | Same as 1 but 3-Apr is ₹1,740 and 3-May ₹1,740 | Same stream; note "amount changed 1,450→1,740 on 3-Apr (likely seat change 10→12)"; expected = 1,740 |
| 3 | Same as 1 but one charge ₹2,900 on 5-Mar after nothing in Feb | Catch-up: counts as Feb+Mar; no price-hike flag; ACTIVE |
| 4 | NEFT `TALLY SOLUTIONS PVT LTD` ₹5,310 on 10-Apr-2024, 08-Apr-2025, 15-Apr-2026 | Tally TSS Silver; YEARLY; next due ≈10-Apr-2027; confidence high; manual pay |
| 5 | Single NEFT `TALLY SOLUTIONS` ₹5,310 on 15-Apr-2026, nothing else | Candidate: Tally TSS; YEARLY from dictionary default; confidence LOW-MEDIUM; next due 15-Apr-2027; asks user only if not fingerprint-matched (₹5,310 fingerprint → MEDIUM, no ask) |
| 6 | NEFT `SHREE INFOTECH` ₹22,500 on 2-Jun-2024, then ₹5,310 on 1-Jun-2025 and 3-Jun-2026 | ₹22,500 → ONE_TIME_LICENCE (Tally Silver); ₹5,310 stream → TSS YEARLY via reseller; next due ~1-Jun-2027 |
| 7 | `SHREE INFOTECH` ₹1,18,000 on 5-Jul only; Tally purchase register has items: 2 laptops ₹1,00,000 + Windows Pro ₹18,000 | No subscription; both lines ONE_TIME (hardware excluded, Windows perpetual one-time) |
| 8 | `SHREE INFOTECH` ₹35,400 on 5-Jul; register items: Seqrite 25 users 1 yr ₹17,700 + M365 ₹17,700 | Two YEARLY candidate streams (Seqrite, M365) each ₹17,700, payee = reseller, product from items |
| 9 | Bank `SHREE INFOTECH` ₹35,400 with no invoice/Tally data | One bundle stream, cycle unknown, ask user once to split; not auto-accepted |
| 10 | Invoice email SolidWorks Subscription Service ₹47,200 (₹40,000+GST) dated 1-Mar; bank NEFT to `CADSPRO TECHNOLOGIES` ₹46,400 on 20-Mar | Match with TDS 2% on 40,000 (=800); occurrence amount_paid 46,400, gross 47,200, tds 800; stream SolidWorks maintenance YEARLY; next due from invoice period_to |
| 11 | Same as 10 but bank ₹43,200 | Match with TDS 10% (4,000); flag "TDS rate 10% — confirm with CA" |
| 12 | Same as 10 but bank ₹47,200 | Match, tds 0 |
| 13 | Same as 10 but bank ₹40,000 | Match as "taxable only" — flag "GST unpaid or RCM/exempt? check"; low confidence match |
| 14 | Card `ADOBE SYSTEMS SOFTWARE IRELAND` USD 54.99 → ₹4,612 (Jan), ₹4,701 (Feb), ₹4,655 (Mar); each with next-day line `FOREIGN CURRENCY MARKUP` ₹161/₹164/₹163 | One MONTHLY stream Adobe CC; group on USD 54.99; INR expected = last; markup folded as fees; total shown incl. fees; gst_mode = vendor-charged (Adobe registered) |
| 15 | Card `NOTION LABS INC` USD 96 yearly, no GST on invoice | YEARLY; gst_mode = RCM; show "18% IGST payable by you ≈ ₹1,430 (ITC claimable)" |
| 16 | `AMAZON INTERNET SERVICES` ₹8,240, ₹11,900, ₹7,300, ₹15,100 on the 3rd–5th of each month | AWS; MONTHLY; variable; expected ≈ median ₹10,070, range 7,300–15,100; no price-hike flags |
| 17 | `WALKOVER WEB SOLUTIONS` ₹5,000 on 12-Jan, 2-Mar, 28-Mar, 30-May | MSG91; PREPAID_CREDITS; no due date; run-rate ≈ ₹3,300/month; "top-up roughly every 46 days" |
| 18 | `GODADDY.COM` ₹1,299 on 14-Aug-2023 and ₹1,499 on 12-Aug-2025 | Domain; BIENNIAL (gap ≈730); next due ≈12-Aug-2027; price change noted |
| 19 | `GODADDY.COM` ₹1,299 once on 14-Aug-2025 with invoice "2 years" | BIENNIAL from invoice text; next due 14-Aug-2027; MEQ = 1,299/24 |
| 20 | Seqrite dealer invoice "EPS 30 users, 3 years" ₹63,720, single payment | TRIENNIAL; next due +3 years; MEQ = 63,720/36 |
| 21 | `ABC COMPUTERS` ₹8,850 on 5-Apr, 6-Jul, 8-Oct, 6-Jan | IT AMC; QUARTERLY; next due ~6-Apr; manual |
| 22 | Web agency ₹11,800 on 1-Apr-2025 and 22-Apr-2026 (21 days late) | YEARLY within ±30 tolerance; ACTIVE; anchor ≈ early April |
| 23 | Yearly stream last paid 10-Apr-2025, today 12-Sep-2026, no payment since | STOPPED (past due + >1 extra… actually >5 months past 10-Apr-2026+30d grace) → OVERDUE until 10-Jul-2026, now flagged "likely stopped — confirm cancelled?" |
| 24 | Monthly stream, last charge 3-Jun-2026, today 12-Sep | 2+ missed → STOPPED; show in "Stopped" list |
| 25 | Monthly stream, last charge 3-Aug-2026, today 12-Sep | Missed 3-Sep + 7 d grace → CHARGE MISSED (auto) |
| 26 | Zoom debit ₹1,769 on 5-Jun, credit ₹1,769 from Zoom on 9-Jun, no later debits | Occurrence cancelled; stream CANCELLED (refunded) |
| 27 | Adobe ₹2 on 1-Jan (auth), ₹1,675 on 8-Jan, 8-Feb… | Ignore ₹2; stream MONTHLY from 8-Jan; "since 1-Jan" |
| 28 | Google Workspace via `RAZORPAY SOFTWARE PVT LTD` ₹2,360 on 5th monthly; invoice emails from Google same amount | Resolve through email match → Google Workspace MONTHLY; payee shown "Google (via Razorpay)" |
| 29 | `PAYU*` ₹2,360 monthly, no emails, no Tally match | Gateway stream candidate; ask user once; after answer, alias saved for (PayU, ₹2,360, day 5) |
| 30 | `PAYPAL *GODADDY` USD 12.99 | Strip gateway → GoDaddy; YEARLY default |
| 31 | M365 via `ABC INFOTECH` ₹17,700 yearly 2023, 2024; then `MSFT*E0…` ₹1,475 monthly from Mar-2025 | Two streams merged into one product M365 with supplier change note; old reseller stream closed, not "stopped" |
| 32 | Tally entry 30-Apr "AWS April bill ₹9,440"; bank `AMAZON INTERNET SERVICES` ₹9,440 on 4-Apr; email invoice 3-Apr | One occurrence; date 4-Apr; sources = 3; spend counted once |
| 33 | Tally entry ₹9,440 on 30-Apr but no bank line within 60 days | Occurrence from Tally with `unpaid_or_unmatched` flag; shown as "booked, not yet paid" |
| 34 | Two bank lines to `CADSPRO` ₹2,00,000 and ₹36,000 on 20-Mar; invoice ₹2,36,000 | Merged single occurrence (split payment) |
| 35 | Two lines ₹23,600 on 1-Mar and ₹23,600 on 15-Apr to same vendor, invoice ₹47,200 | Partial payments merged (within 45 d, sum matches) → one occurrence dated 15-Apr (last part); note "paid in 2 parts" |
| 36 | Owner's personal HDFC card: `CANVA* I03…` ₹4,000 yearly; no Tally entry | Stream ACTIVE, account = owner_personal; warning "not in company books" |
| 37 | Bank `CHQ 000412` ₹8,850, no payee; Tally payment voucher cheque 000412 to "ABC Computers – AMC Q2" | Payee resolved from Tally; joins AMC quarterly stream |
| 38 | Entity A pays Google Workspace 25 seats; entity B has no Workspace payments but users on B's domain | Stream in A; if user marks shared, allocate by seats in per-entity report |
| 39 | Same vendor `ZOHO CORPORATION` ₹2,360 monthly and ₹11,800 yearly | Two streams (Zoho Books monthly; Zoho Mail yearly) — grouping by amount band keeps them apart |
| 40 | `ZOHO` ₹2,360 to Zoho and `CANVA` ₹2,360 same day | Two separate streams; amount never groups across vendors |
| 41 | Quarterly AMC paid 3 months early (Jan instead of Apr) with invoice period Apr–Jun | Next due = Jul (period_to+1), not Apr |
| 42 | Yearly renewal paid 20-Mar for period 1-Apr–31-Mar | FY tag = FY 2026-27 (service period), cash-out month = March |
| 43 | Hostinger ₹1,788 (4-yr promo) once, invoice says "48 months" | Cycle 4-yearly (custom `cycle_months=48`); MEQ = 1,788/48; warn renewal likely at full price |
| 44 | Bank line `CONSOLIDATED CHARGES FOR A/C` ₹590 monthly | Excluded (bank fee pattern) |
| 45 | `TIN NSDL` / `CBDT TDS` challan ₹2,000 | Excluded (government) |
| 46 | Airtel `BHARTI AIRTEL LTD` ₹2,065, ₹2,140, ₹2,065 monthly via NACH `ACH D- AIRTEL` | Telecom/broadband; MONTHLY; variable=true; auto_renew |
| 47 | Two identical `ZOOM.US` ₹1,769 debits on 5-Jun, credit ₹1,769 on 7-Jun | One occurrence (duplicate + reversal) |
| 48 | UPI `UPI/…/tallysolutions.rzp@hdfcbank/…` ₹5,300 vs invoice ₹5,310 | Matched (within ₹50/2%); vendor Tally via VPA slug |
| 49 | Vendor crosses ₹50,000 FY threshold: monthly ₹11,800 paid Apr–Aug, from Sep bank ₹11,600 | TDS 2% detected (₹200 on ₹10,000); no price-cut flag; amounts compared on gross |
| 50 | Cash-out for March: yearly SolidWorks ₹47,200 due 20-Mar, M365 ₹1,740, AWS median ₹10,070, prepaid SMS run-rate ₹3,300 | Cash-out March = 62,310 (+SMS run-rate shown separately as estimate); MEQ = 47,200/12 + 1,740 + 10,070 + 3,300 ≈ 19,043 |
| 51 | New customer uploads only 4 months of bank data with one `GODADDY` charge | Candidate YEARLY (dictionary default), confidence LOW, listed under "needs confirmation"; not auto-accepted |
| 52 | Stream auto-accepted, user edits cycle to HALF_YEARLY | `is_user_modified=true`; engine never overrides; future gap analysis only warns on conflict |

---

## Sources

- TDS on software: [Busy — TDS on software purchase guide](https://busy.in/tds/tds-on-software-purchase-in-india-a-complete-guide-for-businesses/), [eDarpan — TDS on SaaS](https://www.edarpan.com/blog/tds-software-saas-payments-india), [Saral — TDS on software](https://saral.pro/blogs/tds-on-software-purchase/), [Karnani & Co — Sec 195](https://www.karnanica.com/tds-on-purchase-of-software-from-outside-india/), [Taxscan — Engineering Analysis SC ruling](https://www.taxscan.in/no-tds-applicable-on-indian-companies-for-amount-paid-to-use-foreign-software-supreme-court/103203), [Tax Garden — Budget 2025 TDS thresholds](https://taxgarden.in/blog/tds-threshold-changes-fy-2025-26-budget-2025-new-limits-india), [TDSMan — 194J(a)/(b)](https://blog.tdsman.com/2025/07/tds-under-section-194ja-194jb/)
- GST/RCM on foreign SaaS: [zero8.dev — RCM on cloud/SaaS](https://zero8.dev/blog/rcm-on-import-of-services-cloud-saas-india), [IndiaFilings — import of services](https://www.indiafilings.com/gst/import-of-services-under-gst), [ebizfiling — GST on foreign digital purchases](https://ebizfiling.com/blog/gst-implications-on-foreign-digital-service-purchases-by-indian-businesses/), [Tax Garden — GST on IT services SAC](https://taxgarden.in/blog/gst-on-it-software-services-india-rates-sac-codes-2026)
- Recurrence detection: [Plaid recurring transactions blog](https://plaid.com/blog/recurring-transactions/), [Plaid Transactions API](https://plaid.com/docs/api/products/transactions/), [Actual Budget find-schedules.ts](https://raw.githubusercontent.com/actualbudget/actual/master/packages/loot-core/src/server/schedules/find-schedules.ts), [Firefly III recurring transactions](https://docs.firefly-iii.org/how-to/firefly-iii/finances/recurring/), [Subaio detection](https://subaio.com/subaio-explained/how-does-subaio-detect-recurring-payments), [Finexer — recurring detection is a data-quality problem](https://blog.finexer.com/recurring-transaction-detection-bank-data-apis/), [Monarch — recurring help](https://help.monarch.com/hc/en-us/articles/4890751141908-Tracking-Recurring-Expenses-and-Bills)
- Payee strings: [Google payments descriptors](https://support.google.com/paymentscenter/answer/9003663?hl=en-IN), [Google Workspace unrecognised charge](https://knowledge.workspace.google.com/admin/support/troubleshooting/i-dont-recognize-a-google-charge), [AWS re:Post card charge](https://repost.aws/knowledge-center/credit-card-charge-aws), [AWS India/AISPL accounts](https://docs.aws.amazon.com/accounts/latest/reference/managing-accounts-india.html), [Microsoft descriptors](https://yourbankstatementconverter.com/blog/what-does-microsoft-365-show-up-as-on-bank-statement/), [Microsoft Q&A MSFT billing](https://learn.microsoft.com/en-us/answers/questions/543359/unknown-msft-billing-being-charged-to-my-credit-ca), [Adobe descriptors](https://yourbankstatementconverter.com/blog/what-does-adobe-show-up-as-on-bank-statement/), [Adobe community — Ireland Ltd charge](https://community.adobe.com/t5/account-payment-plan-discussions/adobe-systems-software-ireland-ltd-charge/m-p/14834700)
- Pricing/purchase channels: [Mark IT — Tally renewal charges 2026](https://www.markitsolutions.in/blogs/tally-renewal-charges-2026-guide), [Antraweb — TallyPrime pricing](https://www.antraweb.com/blog/tally-prime-pricing), [Cadspro — SOLIDWORKS price India](https://www.cadsprotech.com/solidworks/pricing), [Beacon — SOLIDWORKS reseller](https://beacon-india.com/solidworks-3dcad-software-reseller/), [Cloudfy — Seqrite pricing 2026](https://www.cloudfysystems.com/blog/seqrite-endpoint-pricing-india-2026), [IndiaMART Seqrite listing](https://www.indiamart.com/proddetail/seqrite-endpoint-security-for-total-25-user-for-1-year-19220704291.html), [Autodesk India promotions](https://www.autodesk.com/in/promotions)

Caveats for the developer: descriptor strings marked "(pattern, unverified)" and the bank-specific prefixes (`POS`, `VIN/`, `ACH D-`) come from common Indian statement formats rather than vendor documentation — confirm them against the first real statements you ingest, and keep the tax rates (194J threshold/rates, RCM) in a config table reviewed every Budget.agentId: a386d0d7f72d683d8 (use SendMessage with to: 'a386d0d7f72d683d8', summary: '<5-10 word recap>' to continue this agent)
<usage>subagent_tokens: 105238
tool_uses: 39
duration_ms: 507393</usage>