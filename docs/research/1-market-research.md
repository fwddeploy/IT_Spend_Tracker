# Market research — SaaS / IT spend trackers (Sept 2026)

## Summary in five lines

1. The "SaaS management" category is crowded but almost entirely built for 250–5,000-employee tech companies, priced at $10k–$40k+/year, and discovers apps through SSO logs, browser extensions and US/EU accounting-system integrations — none of which exist in a typical Indian factory.
2. The SMB tier (Substly, Cledara, Hudled, Spendbase, NachoNacho, TrackMySubs) is cheaper but is either manual-entry, needs you to route payments through their cards, or depends on Xero/QuickBooks/Plaid — none support Tally, INR reseller invoices, or on-prem licences with AMC.
3. In India, the only "SaaS spend" products are corporate-card fintechs (Volopay, EnKash, Kodo, RazorpayX, Karbon). They see only card spend, and most CAD/ERP/AMC spend in factories is paid by NEFT/cheque to a reseller, so they miss it.
4. Two hard constraints shape "automatic data in" for India: (a) the RBI Account Aggregator framework does not support company/partnership current accounts, and (b) reading Gmail for invoices triggers Google's restricted-scope CASA audit. The realistic automatic sources are: Tally exports, bank-statement upload, invoice-PDF OCR, GST data and reseller/partner data.
5. Demand evidence is strong in general (Zylo: ~50% of licences unused; 70% of IT leaders rank licence waste as top priority) but thin for Indian factories specifically — nobody has published surveys or forum threads about it.

## Comparison table — existing products

| Product | Target size | Public pricing | How subscriptions get discovered automatically | Notes / gaps for your segment |
|---|---|---|---|---|
| Zluri (Bangalore/US) | 250–2,000+ staff | Not public; est. $4–8/user/month, avg contract ~$38k/yr | SSO/IdP logs, direct API integrations, HRMS, MDM, finance/expense systems, browser extension; excludes email parsing and desktop agents | Limited integrations, 3-month setup complaints. Indian company but 60% revenue from US/EU. |
| Zylo | 500–5,000+ | Median $36k/yr | "Financial discovery": ingests accounts-payable, expense reports and corporate-card data; AI classifies vendors. Only 21% of apps sit behind SSO | "took over a year to get our data into Zylo". Enterprise only. |
| Torii | 100–1,000 IT teams | From ~$2.50/employee/month | IdP, SSO, browser extension, desktop agents via MDM, expense software (NetSuite, Xero, QuickBooks…), matches transactions by description/memo; manual CSV upload | No Tally/Zoho Books India. |
| Productiv | Enterprise | Demo-only | SSO, direct integrations, finance/ERP | Not relevant. |
| CloudEagle.ai | Mid-market/enterprise | Not public | ERP, billing, contracts, bank and card accounts, SSO, 150k-vendor catalog | Indian founders, US-focused. |
| Spendflo (Chennai/US) | 51–500 typical | Custom | ERP, HRIS, CLM integrations; mostly procurement/negotiation service | Not a tracker for factories. |
| Vendr | $400k+/yr SaaS spend | Free tier; $1k–12k/yr platform | Contract upload, benchmarks | Negotiation play. |
| SpendHound | <1,000 staff free | Free under 1,000 employees | QuickBooks, NetSuite, Sage, Brex, AWS; SSO; "15 min integration" | Monetises anonymised data. No India accounting. |
| ManageEngine SaaS Manager Plus (Zoho group) | SMB–mid | Free (2 apps); $250/yr (5 apps) → $7,500/yr (200 apps) | Okta SSO, 25 native integrations, manual vendor entry, invoice upload with OCR, mailbox integration, accounting integration | Closest Indian-owned product; SaaS-only, no on-prem/AMC, no WhatsApp, USD. Study its invoice-OCR path. |
| BetterCloud | Mid/large | Custom | SSO/Google/M365 APIs, finance integrations | Enterprise. |
| Cledara (UK) | 25–300 staff | Basic £100/mo | Virtual cards (primary), Plaid bank link, Xero/QuickBooks | Card-centric; UK/EU/US. |
| Ramp / Brex (US) | Any US company | Free cards | Vendor record from every card transaction; contracts & renewals module | US-only; sees only what is paid through them. |
| Pleo (EU) | SMB | Per-user | Recurring spend from Pleo cards and invoices; renewal reminders; duplicate detection | EU only. |
| Josys (Japan) | ≤300 identities | $100/month | IdP, browser extension, 350+ integrations | IdP-first. |
| Sastrify | $250k+ SaaS spend | ~$750–2,000/mo | ERP/accounting + SSO | Procurement service. |
| NachoNacho (US) | Freelancers → SMB | Free; $199/yr | Virtual/physical Visa cards | US rails. |
| Substly (Sweden) | SMB 2–1,000 | €95–190/mo | Google Workspace / Microsoft Entra sync, browser extensions, SSO login monitoring; no accounting integration | Nearest to your idea; ~₹1 lakh/yr and no INR/Tally; complaint: "takes more effort to input custom software". |
| Hudled (Australia) | Startups/SMB | Free; $19/mo; $79/mo | "We connect directly to your accounting system and sync daily" (Xero-first) | Best proof that accounting-ledger discovery works for SMBs at $19–79/mo. Model to copy, swapping Xero for Tally. |
| Spendbase | Small business | Free tier; paid custom | Mastercard virtual cards, QuickBooks, Google/Microsoft | Complaints: generic onboarding, slow integration setup. |
| TrackMySubs | Individuals/small business | Free → ~$6–10/mo | Manual entry only; reminders | Complaints: no bank sync, quarterly/annual setup unintuitive. |
| Quolum | Startups | Freemium | SaaS-only virtual card | US/Canada only; little activity since 2022. |

## The five discovery methods, and which ones work in an Indian factory

| Method | Used by | Works for a 20–300-staff Indian factory? |
|---|---|---|
| SSO / IdP logs | Zluri, Torii, Josys, Substly, SpendHound | Rarely — most factories have no SSO; CAD/ERP/Tally never log in through SSO. |
| Browser extension | Torii, Zluri, Josys, Substly | Poor — catches web logins only, not desktop apps; privacy hesitation. |
| Desktop agent / MDM | Torii, Zluri | Sees installed CAD but needs an install on every PC — kills zero-install. |
| Card / virtual card | Cledara, Ramp, Pleo, Volopay, EnKash, Kodo | Partial — catches online-card SaaS; misses reseller invoices paid by NEFT/cheque. |
| Accounting / AP ledger ("financial discovery") | Zylo, Torii, Hudled, SpendHound, CloudEagle | Yes — this is the one. In India the ledger is Tally (or Busy/Marg/Zoho Books). |
| Email/inbox parsing | ManageEngine, indie trackers | Feasible but Gmail restricted scopes need a CASA security assessment. Forwarding invoices to a dedicated address avoids this. |
| Invoice OCR | ManageEngine, ContractSafe | Yes — reseller invoices are PDFs/WhatsApp images; OCR + LLM extraction is cheap now. |

## India-specific products

| Product | What it does | What's missing |
|---|---|---|
| Volopay | Virtual cards per vendor, payment reminders, syncs expenses to Tally and Zoho Books | Only sees spend routed through Volopay; no AMC/perpetual renewal calendar. |
| EnKash | Virtual cards, dashboard of upcoming renewals and free trials | Card-only. |
| Kodo | Corporate cards, vendor payments, ERP integration | Startup-oriented. |
| RazorpayX Corporate Card | Cashback on SaaS, spend reports | No renewal tracking. |
| Karbon Business | Corporate card, cross-border | Not a tracker. |
| Zoho Books | Recurring bills, due-date reminders | No licence/seat/AMC concept, nothing consolidated for the owner. |
| ManageEngine SaaS Manager Plus | See above | SaaS-only, USD, IT-admin UI. |
| Tally (TSS) | Reminds inside Tally when TSS expires | Seen by accountant only; nothing cross-vendor. |
| SaaSPay | BNPL for SaaS | Financing, not tracking. |

What's missing in India as a whole: nobody combines (a) Tally-ledger discovery, (b) reseller-invoice OCR, (c) on-prem/perpetual licences + AMC dates, (d) INR/GST-aware totals, and (e) WhatsApp reminders to the owner.

## Small / indie trackers — lessons

- Manual-entry trackers: complaints are "no bank sync", "no bulk edit", "annual/quarterly setup unintuitive". Yet in a hands-on test, manual apps found 14/14 subscriptions while bank-connected Rocket Money found 10/14 — auto-detection misses annual charges. Lesson: statement upload + manual confirm beats "magic" sync that silently misses annual renewals (the expensive ones in a factory).
- Bank-statement upload (LowerMySubs pattern): drop a CSV/PDF statement, scanner finds recurring charges — found 14/14. Pattern to copy.
- Accounting-sync (Hudled): $19–79/month, daily sync.
- Enterprise complaints (anti-patterns): limited integrations, "overwhelming data", year-long onboarding.
- Reddit analysis (MicroGaps): 5–100-person teams "resort to outdated spreadsheets"; recommends a $9–79/month flat tool with 2-minute setup.

## Evidence of demand

- Zylo index: organisations use about half the licences they buy; 70% say cutting licence waste is top priority.
- SolidWorks: since 2016 Dassault charges all missed subscription years (up to a new-licence price) plus the current year to reinstate a lapsed subscription; a user was refused PDM activation by their VAR until three years of back-subscription were paid. Autodesk: an expired subscription must be re-bought as a new order; Indian resellers pushed renewals before the ~10% Jan-2026 price rise. SAP B1 on-prem maintenance is 18–22% of licence value per year — a 10-user AMC is roughly ₹3–3.5 lakh/yr.
- Zoho survey of 5,149 Indian MSMEs: high software cost is the top digital-adoption hurdle; 81% plan to increase cloud spend.
- Ken Research: small SMBs (25–99 staff) spend 4–5% of revenue on digital; medium (101–250) 3–4%, e.g. ERP ₹3–3.5 lakh/yr, cloud ₹8–10 lakh/yr, cybersecurity ₹65–70k/yr. Roughly ₹1–3 lakh/month IT spend for a 100–250-person factory.
- Microsoft 365 in India is usually bought through CSP partners with INR/GST invoices — the reseller, not Microsoft, is the billing source.
- Not found: any Indian factory owner publicly complaining about forgotten licence renewals. Pain may be real but delegated to the accountant/reseller.

## Gaps a new small tool can fill

1. On-prem + perpetual + AMC in one list; nobody models "back-pay if lapsed" (SolidWorks) or "must re-buy as new" (Autodesk).
2. Reseller billing (INR + 18% GST invoices, paid by NEFT) — card tools can't see it; reseller-invoice OCR + forward/WhatsApp intake; resellers as a distribution channel.
3. Tally as the discovery source (XML/Excel export; port 9000 for a later connector).
4. Bank statement upload instead of bank API (AA excludes company current accounts).
5. INR/GST-native totals and pay links (Tally renewal page, Autodesk partner, M365 CSP invoice) + "paid/not paid" tick.
6. WhatsApp reminders to the owner (utility template ≈ ₹0.115 + GST per message).
7. Zero-install, accountant-driven onboarding; aim for "2-minute setup".
8. Price: ₹999–4,999/month flat (not per-employee), far below all competitors and small next to ₹1–3 lakh/month IT spend.

## What to copy / what to avoid

Copy: Zylo/Torii financial discovery; Hudled accounting-sync at flat price; LowerMySubs statement upload with confirm; ManageEngine invoice OCR + forward-to-mailbox; Pleo/Cledara early renewal reminders, duplicate-vendor flags, one named owner per tool; ManageEngine app-count pricing tiers; Josys "visible within minutes" onboarding.

Avoid: SSO/extension/agent discovery; requiring payments through your own card; per-employee or "contact sales" pricing; multi-month implementations and overwhelming dashboards; reading the whole Gmail inbox; silent auto-detection with no review step; SaaS-only data model.

## Sources

Zluri discovery methods https://www.zluri.com/blog/saas-discovery-methods · Zylo financial discovery https://zylo.com/blog/financial-discovery-vs-sso-browser-extensions · Torii discovery https://support.toriihq.com/hc/en-us/articles/4551058926491-Discover-Your-SaaS-Stack · ManageEngine features https://www.manageengine.com/saas-management/features.html and pricing https://www.manageengine.com/saas-management/pricing.html · Hudled https://www.hudled.com/how-it-works · Substly https://www.substly.com/en/pricing/ · Cledara https://www.cledara.com/pricing · LowerMySubs test https://www.lowermysubs.com/blog/best-subscription-trackers-2026 · MicroGaps https://www.microgaps.com/gaps/2026-02-15-saas-subscription-spend-tracker · Volopay https://www.volopay.com/in/subscription-management/ · EnKash https://www.enkash.com/resources/blog/saas-subscription-management-with-virtual-cards · CFO Dive / Zylo index https://www.cfodive.com/news/saas-license-wastage-ranked-as-top-it-spend-challenge/708580/ · SolidWorks late policy https://www.solidsmack.com/cad/the-new-solidworks-subscription-late-policy-and-how-to-avoid-it/ · Zoho MSME survey https://prezohoweb.zoho.com/news/zoho-survey-reveals-that-high-cost-of-software-a-top-hurdle.html · Ken Research https://www.kenresearch.com/pov/smb-digital-spend-monetisation-india · AA state 2026 https://casparser.in/blog/state-of-account-aggregator-2026/ · Gmail CASA https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification · Inc42 on Zluri India https://inc42.com/startups/saas-management-platform-zluri-looks-to-unlock-india-opportunity-after-10-mn-series-a/
