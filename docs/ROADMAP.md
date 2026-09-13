# Roadmap

The product follows a "trust ladder" of data sources: the customer starts with files they already have and adds more automatic sources as they trust the tool. Nothing is ever installed on their PCs.

| Level | Source | Status |
|---|---|---|
| 0 | Bank statement / Tally export upload; manual add; mark paid | **Done** (v0.1–v0.2) |
| 1 | Unique inbound email address per company (`bills-xxxx@…`) + Gmail/Outlook forwarding rule; invoice PDFs parsed; bank alert emails | Next |
| 1 | WhatsApp intake: accountant sends a bill photo → OCR/LLM extraction → line | Next |
| 2 | GST portal: pull GSTR-2B monthly via a GSP (customer enables API access + OTP) → every Indian-billed software invoice with vendor GSTIN | Planned |
| 3 | Click-Allow connectors: Zoho Books (bills, payments), Microsoft 365 admin (licence counts, renewal date) | Planned |
| 4 | Opt-in installs for customers who ask: Tally live connector (port 9000), PC agent for installed software / seat usage; Gmail direct connect (after Google CASA) | Later |

Product items still open (small):
- Multi-company shared licence detection for CAs; global promotion of frequently-confirmed aliases into `vendors.yaml`; LLM fallback for unknown payees.
- Money columns to `Numeric`; background job for very large uploads; rate limiting.
- Benchmarks ("factories your size pay ₹X"), renewal negotiation tips.

Research behind these choices: `docs/research/2-integration-options.md` (what each source gives, what the customer has to do, cost, verdict).
