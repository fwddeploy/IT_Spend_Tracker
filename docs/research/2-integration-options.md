# Zero-install data sources for an Indian MSME software-spend tracker (Sept 2026)

Verdicts: V1 = build now · Later = after v1 · Skip = not worth it. [unverified] = could not confirm from a primary source.

## A. Email as a data source

### A1. Gmail API (Google Workspace and free Gmail)
- Every Gmail scope that reads email content is "restricted" (gmail.readonly, gmail.metadata, gmail.modify). Restricted scopes require brand verification, restricted-scope review, and an annual third-party security assessment (CASA) for any normal SaaS backend — "potentially several weeks".
- CASA cost (2026): roughly $540–$1,800 for a lab-conducted assessment (up to ~$4,500 for a full manual audit); redone every 12 months. Small teams do pass it.
- Before verification you can run in "testing" with a 100-user cap and an "unverified app" warning screen.
- Loophole for Workspace customers: a Workspace super-admin can mark your unverified app as "trusted" in Admin console; users can then grant restricted scopes without Google verification. Not available for free Gmail.
- Verdict: Later (start verification early; don't block v1 on it).
- Sources: https://developers.google.com/workspace/gmail/api/auth/scopes · https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification · https://support.google.com/cloud/answer/13464321 · https://deepstrike.io/blog/google-casa-security-assessment-2025 · https://truto.one/blog/our-google-oauth-app-is-live-and-casa-tier-2-certified/ · https://knowledge.workspace.google.com/admin/apps/authorize-unverified-third-party-apps

### A2. Microsoft Graph (Outlook / Microsoft 365)
- Mail.Read (delegated) does not technically require admin consent, but since MC1097272 (July–Aug 2025) new tenants default to "Do not allow user consent", so in practice an M365 admin must approve your app. Application permission Mail.Read always needs admin consent.
- Your multi-tenant app should be publisher-verified (Partner Center account + MPN ID). No paid security audit like CASA.
- Customer steps: admin clicks an admin-consent URL → signs in as Global Admin → Accept.
- Verdict: V1-capable (much cheaper than Gmail), but needs the customer's M365 admin — usually the owner or their IT reseller.
- Sources: https://www.appgovscore.com/blog/microsoft-disables-user-consent-by-default-are-you-ready-for-mc1097272 · https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/user-admin-consent-overview · https://learn.microsoft.com/en-us/graph/permissions-reference

### A3. Cheapest option: forwarding rule to a unique inbound address
- Each customer gets bills-<id>@in.yourapp.in. They create a Gmail filter or Outlook rule; every matching email (with PDF) lands in your inbound-parse webhook.
- Gmail: user auto-forwarding is on by default in Workspace. Adding a forwarding address triggers a verification email to your inbound address — you receive it, so your app can show/confirm the code instantly.
- Outlook/M365 gotcha: automatic external forwarding is blocked by default in new tenants (NDR 5.7.520). Admin must turn it on in outbound spam policy or allow your domain. Workaround with no admin action: manual forward.
- Inbound parsing services: Postmark $1.25 per 1,000 messages; SendGrid Inbound Parse free on paid plans ($19.95/mo); Mailgun inbound included in sending plans; CloudMailin free 10k/mo but 512 KB max message (too small for many PDFs), paid $25–85.
- Customer steps (Gmail): open our link → copy address → Gmail Settings → Forwarding → add address → enter code we show → create filter with our search string. About 3 minutes. Fallback: forward invoices by hand or via WhatsApp.
- Limitations: only catches emails the filter matches; user can silently break it; forwarded mail sometimes loses original headers.
- Verdict: V1.
- Sources: https://knowledge.workspace.google.com/admin/gmail/let-users-automatically-forward-their-own-gmail-emails · https://learn.microsoft.com/en-us/defender-office-365/outbound-spam-policies-external-email-forwarding · https://mails.ai/blog/best-inbound-email-parsing-api-for-developers · https://www.cloudmailin.com/plans-and-pricing

### A4. What vendor invoice emails look like [sender names/subjects unverified — confirm with real samples]

| Vendor | Typical email | Reliable fields | GST entity (matters for GSTR-2B) |
|---|---|---|---|
| Microsoft 365 direct | "Your Microsoft invoice is available" with PDF/link | Invoice no., period, amount, products, seats | Invoiced by Microsoft Regional Sales Pte. Ltd. (Singapore); GSTIN can be added |
| Microsoft 365 via Indian CSP | Reseller's own GST tax invoice PDF | Vendor GSTIN, amount, GST | Indian GSTIN → appears in GSTR-2B |
| Google Workspace | Monthly invoice from payments-noreply@google.com with PDF | Invoice no., seats, plan, amount, GST | Google India Pvt Ltd; GST charged → appears in GSTR-2B |
| AWS | "Amazon Web Services Invoice Available" | Account ID, amount, period | AWS India Pvt Ltd charges GST; appears in GST portal |
| Azure | Invoice email + portal | Amount, period | Microsoft Corporation India Pvt Ltd [secondary source] |
| Adobe direct | "Your Adobe invoice" | Amount, plan, renewal date | [unverified] |
| Autodesk, Zoho, GoDaddy, Quick Heal, Kaspersky | Renewal reminders ~30/7 days before; invoice on charge | Product, expiry, amount | Zoho India charges GST; others [unverified] |
| Tally TSS | In-product notification; partner reminder emails. Silver ₹4,500 + GST, Gold ₹13,500 + GST per year | Serial no., expiry | — |
| SolidWorks | Invoice comes from the VAR (reseller), not Dassault | VAR GSTIN, serials, term | Indian GST invoice → GSTR-2B |

Bank debit / card alert emails (HDFC InstaAlert, ICICI alerts): fixed pattern with amount, masked account/card last-4, merchant or UPI VPA, date/time, reference. Reliable: amount, date, last-4, merchant text. Not reliable: vendor identity (needs mapping table), no invoice number, no GST.

## B. Bank data without install

### B1. Account Aggregator (AA) — 2026 status
- Only regulated entities (RBI/SEBI/IRDAI/PFRDA) can be FIUs. A TSP (Setu, Finvu, OneMoney, Digio, Perfios) builds the tech but cannot lend you a licence.
- Current accounts are live only for sole proprietors. Partnership, LLP, Pvt Ltd and trust current accounts are excluded. Most factories are Pvt Ltd/partnership → no data.
- Consent must use a Sahamati purpose code (e.g. Account Monitoring CT003).
- Cost/time if you had a regulated partner: a few rupees to tens of rupees per consent; first-year budget ₹5–25 lakh and 5–10 months.
- Verdict: Skip for v1; revisit only if non-individual current accounts go live and you have a regulated partner.
- Sources: https://sahamati.org.in/faq/ · https://sahamati.org.in/account-types-activated-by-banks-on-aas/ · https://casparser.in/blog/state-of-account-aggregator-2026/ · https://docs.setu.co/data/account-aggregator/licenses-and-go-live/go-live

### B2. Bank statement downloads and emailed statements
- Formats confirmed: SBI PDF and Excel; HDFC PDF, Excel, Text/delimited, CSV (app); ICICI PDF, Excel, CSV. Axis, Kotak, Yes, IndusInd, BoB, PNB: PDF + Excel/XLS [not individually verified].
- PDF password conventions (emailed e-statements): HDFC = Customer ID; SBI = DOB or account number; ICICI, Axis, Kotak, Yes, IndusInd, BoB, PNB = DOB DDMMYYYY (retail). For company current accounts often customer ID or PAN-based [verify per bank].
- Most banks email a monthly e-statement if registered — forward via the same A3 rule [bank-by-bank confirmation not obtained].
- Parsing: commercial bank-statement analyser APIs (Perfios, Digitap, Signzy, HyperVerge — enterprise pricing); converters (BankConv); DIY with pdfplumber/camelot. Excel exports are far easier than PDFs — ask customers for Excel.
- Customer steps: once a month, net banking → Account Statement → Excel → upload or email to unique address. Or forward the bank's auto e-statement and give us the password once.
- Verdict: V1 — the only bank source that works for Pvt Ltd/partnership accounts with zero install.
- Sources: https://www.bankstatementlab.com/en/blog/en-download-bank-statement-sbi-hdfc-icici · https://mybankstatementanalysis.com/blog/indian-bank-statement-pdf-passwords · https://www.digitap.ai/bank-statement-analyzer-api.html

### B3. Corporate/business cards
- Card statements and per-transaction alert emails work the same way. Merchant descriptors are the best "which SaaS is this" signal. Verdict: V1 (via forwarded alerts/statements).

## C. Accounting software without install

### C1. Tally (TallyPrime)
- Export (Ctrl+E) any report — Purchase Register, Ledger vouchers, Bills Payable/Outstandings, Day Book — to Excel, PDF, XML, JSON, HTML, text (no CSV). E-mail (Ctrl+M) any report directly from Tally (Gmail/Outlook OAuth or SMTP).
- No native scheduling — every export/email is manual.
- XML export of purchase vouchers carries party name, GSTIN, voucher no., date, amount, ledger — richest format.
- TDL add-on = Tally's scripting file loaded into Tally; a change on the customer's PC → treat as later.
- Tally XML/HTTP server (port 9000) answers XML requests when Tally is open and configured as server — only realistic with an install-based agent or Tally-on-cloud.
- Tally-on-cloud providers (RDP-hosted, ~₹400/user/month) don't promise API/port exposure [unverified].
- Customer steps (v1): accountant opens Purchase Register or the "Software Expenses" ledger → Ctrl+E → Excel/XML → email to unique address (or Ctrl+M directly). Monthly, ~2 minutes.
- Verdict: V1 (manual export + our instructions); port-9000 connector = Later.
- Sources: https://help.tallysolutions.com/export-data-in-tally/ · https://help.tallysolutions.com/e-mailing-in-tallyprime/ · https://help.tallysolutions.com/integration-methods-and-technologies/

### C2. Zoho Books
- REST API v3, OAuth 2.0; India DC accounts.zoho.in / zohoapis.in; read scopes per module (bills, expenses, vendorpayments, contacts). Endpoints /books/v3/bills, /expenses, /vendorpayments.
- Rate limits: 100 req/min; per-day per org by plan (Free 1,000 → Premium 10,000).
- Customer steps: click "Connect Zoho Books" → Zoho login → Accept. Verdict: V1.
- Sources: https://www.zoho.com/books/api/v3/oauth/ · https://www.zoho.com/books/api/v3/bills/ · https://www.getknit.dev/blog/zoho-books-api-directory-9eeBzn

### C3. Busy, Marg, Vyapar, SAP B1, Business Central
- Busy: no public REST API; Excel export in v1.
- Marg desktop: no public API; MargBooks (cloud) has an Open API → Excel export v1.
- Vyapar: no public API found → Excel/PDF export.
- SAP B1: Service Layer (OData, port 50000) but on-prem → needs VPN; Later; Excel export v1.
- Dynamics 365 BC cloud: API v2.0 with admin-consented Entra app; Later.

## D. Vendor-side APIs

| Vendor | What a third-party app can read | Customer action | Verdict |
|---|---|---|---|
| Microsoft 365 | /subscribedSkus → SKU, consumed and prepaid units; /directory/subscriptions → nextLifecycleDateTime (renewal), totalLicenses, isTrial, status. No prices. Needs admin consent. | Global admin grants consent once | V1 (best vendor API available) |
| Microsoft Partner Center billing | Only for CSP partners about their customers | — | Skip |
| Google Workspace | No customer-facing subscription/renewal API; Reseller API is resellers-only | Invoice email is the source | Use email |
| Adobe | User Management API: enterprise plans only; no counts/prices/renewals | — | Skip; use email |
| Autodesk | No public subscription/renewal API [inferred] | — | Skip; use email/reseller invoice |
| AWS | Cost Explorer API via cross-account IAM role; $0.01 per request | Create IAM role | Later |
| Azure | Cost Management APIs; customer assigns Cost Management Reader to your service principal | Admin role assignment | Later |
| Slack | team.billing.info returns only plan name | — | Skip |
| Atlassian, Figma, Canva | Users/directory only; no billing | — | Skip |
| Zoho (as vendor) | GST invoices by email | — | Use email |

SolidWorks in India: sold and invoiced only through authorised VARs; annual "Subscription Service" per licence; SolidNetWork Licensing for floating seats. Late policy since 2016: lapsed subscriptions must pay all missed years plus current year — a strong "renew on time" selling point. VAR is GST-registered → invoice appears in GSTR-2B.
Sources: https://learn.microsoft.com/en-us/graph/api/subscribedsku-list · https://learn.microsoft.com/en-us/graph/api/directory-list-subscriptions · https://www.solidworks.com/how-to-buy/subscription-services-faq · https://www.solidsmack.com/cad/the-new-solidworks-subscription-late-policy-and-how-to-avoid-it/

## E. WhatsApp (Meta Cloud API via Indian BSPs)
- Pricing (2026, India, per-message): Marketing ≈ ₹0.78–0.86; Utility ≈ ₹0.115 (free inside an open 24-h service window); Service (customer-initiated replies within 24 h) = free.
- BSP platform fees: AiSensy from ₹999/mo (+~₹0.20/msg), Interakt ~₹2,142–3,532/mo, Wati ₹2,499–4,999/mo, Gupshup ₹4,000–6,000/mo. Direct Meta Cloud API has no platform fee.
- Receiving bill photos: webhook gets a media ID; download via Graph API; run OCR/LLM extraction. Reply within 24 h is free. Reminders you initiate are Utility templates needing approval (hours to days; 20–30% first-time rejections; number setup 5–15 days).
- Customer steps: save your number, send "Hi", forward invoices/photos. Verdict: V1 (intake + reminders).
- Sources: https://developers.facebook.com/docs/whatsapp/pricing · https://codingclave.com/guides/whatsapp-api-pricing-india-2026-comparison

## F. Other zero-install discovery tricks

### F1. GST portal GSTR-2B via a GSP — checked carefully
- GSTR-2B = auto-drafted monthly statement generated on the 14th of the following month, containing every B2B invoice that GST-registered suppliers filed against the customer's GSTIN.
- API returns per supplier: GSTIN, trade name; per document: invoice number, date, invoice value, taxable value, IGST/CGST/SGST, ITC available flag.
- Consent flow: customer logs in to gst.gov.in → My Profile → Manage API Access → Enable, session 6 hours to 30 days. In your app: enter GSTIN + GST username → OTP to registered mobile/email → your GSP issues a session token → pull GSTR-2B monthly. Catch: session expires after at most 30 days, so the customer or their CA re-enters an OTP monthly (same friction ClearTax/Zoho Books users already accept).
- Shows: every purchase from an Indian GST-registered seller — Google India (Workspace), AWS India, Microsoft India (Azure), any Microsoft CSP/reseller, Adobe/Autodesk/SolidWorks resellers, Tally partners, Zoho, Quick Heal, GoDaddy India. Vendor GSTIN + name + invoice number/date/amount.
- Does not show: imports of services from foreign entities (Microsoft direct from Singapore [GST treatment unverified], Adobe/Figma/Canva/Slack paid by card to foreign entities); late-filing vendors (show a month later); line-item descriptions (totals only).
- GSPs/ASPs with developer portals: Sandbox (sandbox.co.in), Masters India, ClearTax (enterprise), Adaequare uGSP, WhiteBooks, FinAGG, Cygnet. Per-call prices not published — expect a small monthly minimum plus a few rupees per call [get quotes]. You sign up as a client of a GSP; no need to become one.
- Verdict: V1 — the only source that gives structured, vendor-identified spend for every Indian-invoiced software purchase, with a consent flow the customer's CA already knows. Combine with email for foreign-billed SaaS.
- Sources: https://tutorial.gst.gov.in/userguide/returns/FAQ_gstr2b.htm · https://developer.sandbox.co.in/api-reference/gst/compliance/endpoints/taxpayer/gstr-2b/document · https://learn.quicko.com/gst-portal-manage-api-access · https://cleartax.in/s/gst-api-access · https://developer.sandbox.co.in/reference/gst-taxpayer-authentication · https://www.mastersindia.co/goods-and-services-tax-gst-api/

### F2. SSO / identity logs
- Google Workspace Reports API token audit lists third-party apps users authorised with Google sign-in (180-day lookback; super-admin grants admin.reports.audit.readonly; free on all tiers).
- Microsoft Entra sign-in logs need AuditLog.Read.All and an Entra ID P1/P2 licence (Business Basic/Standard tenants get an error).
- Tells you which apps are used, not what they cost. Verdict: Later.

### F3. DNS
- MX/SPF/CNAME records reveal some vendors (Google/Microsoft mail, Zoho, Atlassian, Freshdesk) with no consent — a free "we already know you use X" onboarding demo trick, not spend. Verdict: V1 as a demo hook only.

## Recommended v1 stack (all zero-install)
1. Unique inbound email address + Gmail/Outlook forwarding rule (Postmark or SendGrid Inbound Parse) for vendor invoices, bank alerts and monthly e-statements.
2. WhatsApp number for bill photos and renewal reminders.
3. GSTR-2B pull via a GSP (customer enables API access + monthly OTP) for all Indian-invoiced software vendors and resellers.
4. Microsoft Graph admin consent (subscribedSkus + directory/subscriptions) and Zoho Books OAuth.
5. Manual monthly exports: Tally Purchase Register / ledger in Excel or XML (Ctrl+E or Ctrl+M straight to the inbound address), bank statement Excel.

Defer: Gmail OAuth (CASA), Tally port-9000 connector, AA framework, AWS/Azure cost APIs, SSO log discovery.

## Could not verify
- Exact sender addresses/subject lines of vendor invoice emails.
- Whether Microsoft Regional Sales Pte Ltd charges GST to Indian B2B customers or invoices under reverse charge (affects whether direct M365 shows in GSTR-2B); same for Adobe direct.
- Per-API-call prices of any GSP.
- Statement formats and PDF-password rules for corporate current accounts at Axis, Kotak, Yes, IndusInd, BoB, PNB.
- Whether Tally-on-cloud providers will expose port 9000 to a third party.
- Vyapar API status; Canva/Atlassian billing APIs.
