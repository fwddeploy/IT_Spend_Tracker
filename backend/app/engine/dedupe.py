"""Turn raw rows from several sources into occurrences (one per real payment).

Rules implemented (numbers refer to research/3-engine-logic-and-test-cases.md):
- excluded / bank-fee / government rows dropped (2.35, 2.44)
- forex markup lines folded into the previous foreign debit as fees (2.31)
- tiny authorisation charges (<= Rs 5) dropped (2.25)
- refund credit cancels the matching debit; same-day duplicate debit + reversal keeps one (2.24, 2.47)
- same bill in bank + tally + email/gst merged; bank date and amount win, invoice fields kept (2.38, 2.39)
- GST / TDS relations when matching an invoice to a bank debit (2.32, 2.34)
- split payments summing to an invoice merged (2.22, 2.23)
- tally/email rows with no bank line within the window become "unpaid / booked-not-paid" occurrences (2.33)
- bank cheque line + Tally voucher with the same cheque number -> Tally supplies the payee (2.37)
- hardware-only bills go to the one-time "hardware" bucket; mixed bills are flagged (2.29)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from rapidfuzz import fuzz

from app.engine.vendors import Catalog, Resolution
from app.engine.normalize import AUTO_MODES, payee_tokens, instrument_no as _instrument_from_text, same_instrument

WINDOW = {  # days, by source pair
    ("bank", "email"): 15, ("bank", "gst"): 60, ("bank", "tally"): 60, ("card", "email"): 15,
    ("card", "gst"): 60, ("card", "tally"): 60, ("tally", "email"): 60, ("tally", "gst"): 45, ("email", "gst"): 45,
}
PAYMENT_SOURCES = {"bank", "card", "manual"}
BILL_SOURCES = {"tally", "email", "gst"}
TDS_RATES = (0.01, 0.02, 0.10, 0.20)


@dataclass
class Row:
    id: int
    source: str
    date: date
    amount: float
    direction: str
    payee_clean: str
    raw_description: str = ""
    currency: str = "INR"
    fx_amount: float | None = None
    payment_mode: str | None = None
    invoice_no: str | None = None
    period_from: date | None = None
    period_to: date | None = None
    taxable: float | None = None
    gst: float | None = None
    ledger: str | None = None
    is_personal: bool = False
    account_id: int | None = None
    account_label: str | None = None
    instrument_no: str | None = None   # cheque number (bank ref column / Tally bank allocation); derived from narration if None
    res: Resolution = field(default_factory=Resolution)


@dataclass
class Occ:
    date: date
    amount_paid: float
    amount_gross: float
    payee_clean: str
    vendor_key: str | None
    product: str | None
    resolution: str
    sources: list[str]
    raw_row_ids: list[int]
    raw_description: str
    currency: str = "INR"
    fx_amount: float | None = None
    taxable: float | None = None
    gst: float | None = None
    tds: float | None = None
    fees: float = 0.0
    payment_mode: str | None = None
    auto_renew: bool = False
    invoice_no: str | None = None
    period_from: date | None = None
    period_to: date | None = None
    is_personal: bool = False
    unpaid: bool = False
    account_label: str | None = None
    flags: list[str] = field(default_factory=list)
    res: Resolution = field(default_factory=Resolution)
    product_soft: bool = False   # product text came from a narration, not from vendor recognition
    instrument_no: str | None = None
    fy: str | None = None        # "2026-27": financial year of the service period (set by build_streams)


def _narration_product(raw: str) -> str | None:
    """'Cadspro Technologies | SolidWorks Subscription Service 1 seat' -> 'SolidWorks Subscription Service 1 seat'."""
    if not raw:
        return None
    text = raw.split("|", 1)[1].strip() if "|" in raw else ""
    text = text.strip(" -")
    return text[:80] if len(text) >= 4 else None


def _same_vendor(a: Row | Occ, b: Row | Occ) -> bool:
    ka = a.res.vendor_key
    kb = b.res.vendor_key
    if ka and kb:
        return ka == kb
    pa, pb = a.payee_clean, b.payee_clean
    if not pa or not pb:
        return False
    ta = " ".join(t for t in payee_tokens(pa) if len(t) > 2)
    tb = " ".join(t for t in payee_tokens(pb) if len(t) > 2)
    return fuzz.token_set_ratio(ta, tb) >= 85


def _window(s1: str, s2: str) -> int:
    if s1 == s2:
        return 0
    return WINDOW.get((s1, s2)) or WINDOW.get((s2, s1)) or 15


def _amount_relation(bank: float, bill: Row) -> tuple[bool, float | None, float | None, float | None]:
    """Does a bank debit match a bill row allowing GST and TDS? Returns (match, taxable, gst, tds)."""
    total = bill.amount
    taxable = bill.taxable
    gst = bill.gst
    if taxable is None:
        # assume invoice total includes 18% GST unless it's a foreign no-GST vendor
        taxable = round(total / 1.18, 2)
        gst = round(total - taxable, 2)
    plain = [(total, 0.0), (taxable * 1.18, 0.0), (taxable, 0.0)]
    with_tds = []
    for r in TDS_RATES:
        with_tds.append((total - taxable * r, taxable * r))
        with_tds.append((taxable * 1.18 - taxable * r, taxable * r))
    strict = max(3.0, total * 0.003)
    for exp, tds in plain[:2] + with_tds:      # exact-ish first (TDS rates are exact percentages)
        if abs(bank - exp) <= strict:
            return True, taxable, gst, (round(tds, 2) if tds else None)
    loose = max(50.0, total * 0.02)            # rounded UPI / cash discount (2.48)
    for exp, tds in plain[:2]:
        if abs(bank - exp) <= loose:
            return True, taxable, gst, None
    if abs(bank - taxable) <= strict:          # paid taxable only (GST unpaid / RCM) — weakest match
        return True, taxable, gst, None
    return False, None, None, None


def _match_quality(bank: float, bill: Row) -> int:
    """3 = full amount (with or without TDS), 1 = taxable-only, 0 = none."""
    ok, taxable, gst, tds = _amount_relation(bank, bill)
    if not ok:
        return 0
    if taxable is not None and abs(bank - taxable) <= max(3.0, bill.amount * 0.003) and abs(bank - bill.amount) > max(3.0, bill.amount * 0.003):
        return 1
    return 3


def _route_hardware(r: Row, catalog: Catalog) -> None:
    """2.29: a bill whose text is hardware-only becomes a one-time hardware purchase; hardware + software words on
    one bill keep the software vendor but are flagged. Unknown bank payees whose narration says LAPTOP/PRINTER etc.
    are hardware too."""
    if r.res.is_fee or r.res.excluded or r.direction == "credit":
        return
    text = f"{r.raw_description or ''} {r.ledger or ''}"
    if not catalog.is_hardware_text(text):
        return
    if r.source in BILL_SOURCES:
        if catalog.is_software_text(text):
            if r.res.vendor_key != "hardware" and "mixed_hardware_bill" not in r.res.flags:
                r.res.flags.append("mixed_hardware_bill")
            return
        r.res = Resolution(vendor_key="hardware", product=r.res.product or "Hardware purchase", method="hardware",
                           confidence=0.9, suggested_cycle="one_time", looks_it=True, term_months=None)
    elif not r.res.vendor_key and not catalog.is_software_text(text):
        r.res = Resolution(vendor_key="hardware", product="Hardware purchase", method="hardware",
                           confidence=0.7, suggested_cycle="one_time", looks_it=True)


def build_occurrences(rows: list[Row], catalog: Catalog, today: date | None = None) -> list[Occ]:
    today = today or date.today()
    rows = sorted(rows, key=lambda r: (r.date, r.id))
    for r in rows:
        if r.instrument_no is None and (r.source in BILL_SOURCES or r.payment_mode == "cheque"):
            r.instrument_no = _instrument_from_text(r.raw_description)
        _route_hardware(r, catalog)
    debits: list[Row] = []
    credits: list[Row] = []
    fees: list[Row] = []
    for r in rows:
        if r.res.is_fee:
            fees.append(r)
        elif r.direction == "credit":
            # credits are only ever used as refunds/reversals of a vendor debit, so the exclusion list
            # ("REVERSAL", "CHEQUE RETURN"...) must not hide them
            credits.append(r)
        elif r.res.excluded:
            continue
        elif r.amount <= 5:
            continue
        else:
            debits.append(r)

    # --- refunds / reversals (2.24, 2.47): a credit cancels the nearest matching debit in the previous 30 days.
    # Two identical same-day debits + one credit therefore leave one occurrence (a retried card charge); two
    # identical debits with no credit stay two occurrences (two seats billed separately).
    dropped: set[int] = set()
    for c in credits:
        cands = [d for d in debits if d.id not in dropped and d.source in PAYMENT_SOURCES
                 and abs(d.amount - c.amount) <= max(2.0, d.amount * 0.01) and 0 <= (c.date - d.date).days <= 30
                 and _same_vendor(d, c)]
        if cands:
            dropped.add(min(cands, key=lambda d: (c.date - d.date).days).id)
    debits = [d for d in debits if d.id not in dropped]

    # --- build occurrences: payments first, then attach bills ---
    occs: list[Occ] = []
    payments = [d for d in debits if d.source in PAYMENT_SOURCES]
    bills = [d for d in debits if d.source in BILL_SOURCES]

    for p in payments:
        # (re-uploads of the same statement are already de-duplicated at ingest by their dedupe_key)
        occs.append(Occ(
            date=p.date, amount_paid=p.amount, amount_gross=p.amount, payee_clean=p.payee_clean,
            vendor_key=p.res.vendor_key, product=p.res.product, resolution=p.res.method,
            sources=[p.source], raw_row_ids=[p.id], raw_description=p.raw_description,
            currency=p.currency, fx_amount=p.fx_amount, payment_mode=p.payment_mode,
            auto_renew=(p.payment_mode in AUTO_MODES), is_personal=p.is_personal,
            account_label=p.account_label, res=p.res, instrument_no=p.instrument_no,
            flags=list(p.res.flags) if getattr(p.res, "flags", None) else [],
        ))

    # --- fold forex markup lines into the previous foreign debit (2.31) ---
    for f in fees:
        cand = [o for o in occs if 0 <= (f.date - o.date).days <= 3 and f.amount <= o.amount_paid * 0.06]
        if cand:
            o = max(cand, key=lambda o: o.date)
            o.fees += f.amount
            o.raw_row_ids.append(f.id)
            if "forex_markup" not in o.flags:
                o.flags.append("forex_markup")

    # --- attach bills (tally / email / gst) to payments; unmatched bills become unpaid occurrences ---
    for b in bills:
        matched = None
        # 0. cheque number (2.37): a bank cheque line has no payee; the Tally voucher with the same instrument
        #    number supplies party / vendor / product. Amount must still relate (cheque numbers repeat across books).
        if b.instrument_no:
            for o in occs:
                if o.instrument_no and same_instrument(o.instrument_no, b.instrument_no) \
                        and abs((o.date - b.date).days) <= 90 and _amount_relation(o.amount_paid, b)[0]:
                    matched = o
                    ok, taxable, gst, tds = _amount_relation(o.amount_paid, b)
                    o.taxable, o.gst, o.tds = taxable, gst, tds
                    if tds:
                        o.amount_gross = round(o.amount_paid + tds, 2)
                    if not o.vendor_key or o.payee_clean.startswith("CHQ "):
                        o.payee_clean = b.payee_clean
                    o.flags.append("cheque_matched")
                    break
        # 1. exact invoice number
        if not matched and b.invoice_no:
            matched = next((o for o in occs if o.invoice_no and o.invoice_no == b.invoice_no), None)
        # 2. vendor + amount relation + date window
        if not matched:
            best = None
            for o in occs:
                if any(s in BILL_SOURCES and s == b.source for s in o.sources):
                    continue  # a bill row shouldn't merge into another bill of the same source
                w = max(_window(b.source, s) for s in o.sources)
                if abs((o.date - b.date).days) > w:
                    continue
                if not _same_vendor(o, b):
                    continue
                ok, taxable, gst, tds = _amount_relation(o.amount_paid, b)
                if ok:
                    q = _match_quality(o.amount_paid, b)
                    dist = abs((o.date - b.date).days)
                    if best is None or (-q, dist) < (-best[5], best[0]):
                        best = (dist, o, taxable, gst, tds, q)
            if best and best[5] < 3:
                # weak (taxable-only) match: a split payment that sums to the bill is more likely — checked below first
                weak = best
                best = None
            else:
                weak = None
            if best:
                _, matched, taxable, gst, tds, _q = best
                matched.taxable, matched.gst, matched.tds = taxable, gst, tds
                if tds:
                    matched.amount_gross = round(matched.amount_paid + tds, 2)
                    matched.flags.append(f"tds_{int(round(tds / taxable * 100)) if taxable else ''}pct")
                elif abs(matched.amount_paid - (taxable or 0)) <= max(5.0, (taxable or 0) * 0.02) and gst:
                    matched.flags.append("paid_taxable_only_check_gst")
        # 3. split payments: two payments summing to this bill within 45 days (2.22/2.23)
        if not matched:
            pool = [o for o in occs if _same_vendor(o, b) and abs((o.date - b.date).days) <= 60
                    and all(s in PAYMENT_SOURCES for s in o.sources)]
            for i in range(len(pool)):
                for j in range(i + 1, len(pool)):
                    a, c = pool[i], pool[j]
                    if abs((a.date - c.date).days) <= 45:
                        ok, taxable, gst, tds = _amount_relation(a.amount_paid + c.amount_paid, b)
                        if ok:
                            keep, other = (a, c) if a.date >= c.date else (c, a)
                            keep.amount_paid = round(a.amount_paid + c.amount_paid, 2)
                            keep.amount_gross = round(keep.amount_paid + (tds or 0), 2)
                            keep.raw_row_ids += other.raw_row_ids
                            keep.flags.append("paid_in_2_parts")
                            keep.taxable, keep.gst, keep.tds = taxable, gst, tds
                            occs.remove(other)
                            matched = keep
                            break
                if matched:
                    break
            if not matched and weak:
                _, matched, taxable, gst, tds, _q = weak
                matched.taxable, matched.gst, matched.tds = taxable, gst, tds
                matched.flags.append("paid_taxable_only_check_gst")
        if matched:
            matched.sources.append(b.source)
            matched.raw_row_ids.append(b.id)
            matched.invoice_no = matched.invoice_no or b.invoice_no
            matched.period_from = matched.period_from or b.period_from
            matched.period_to = matched.period_to or b.period_to
            for fl in getattr(b.res, "flags", []) or []:
                if fl not in matched.flags:
                    matched.flags.append(fl)
            # bill rows often carry the better vendor/product (Tally narration, invoice text)
            if b.res.vendor_key and (not matched.vendor_key or matched.res.confidence < b.res.confidence):
                matched.vendor_key, matched.product, matched.resolution = b.res.vendor_key, b.res.product or matched.product, "cross"
                matched.res = b.res
            elif b.res.product and not matched.product:
                matched.product = b.res.product
            if not matched.product:
                matched.product = _narration_product(b.raw_description)
                matched.product_soft = matched.product is not None
            if b.taxable and not matched.taxable:
                matched.taxable, matched.gst = b.taxable, b.gst
            if b.res and b.res.term_months and matched.res and not matched.res.term_months:
                matched.res.term_months = b.res.term_months
        else:
            occs.append(Occ(
                date=b.date, amount_paid=b.amount, amount_gross=b.amount, payee_clean=b.payee_clean,
                vendor_key=b.res.vendor_key, product=b.res.product or _narration_product(b.raw_description), product_soft=(b.res.product is None), resolution=b.res.method,
                sources=[b.source], raw_row_ids=[b.id], raw_description=b.raw_description,
                currency=b.currency, taxable=b.taxable, gst=b.gst, invoice_no=b.invoice_no,
                period_from=b.period_from, period_to=b.period_to, unpaid=(b.date >= today - timedelta(days=60)),
                account_label=b.account_label, res=b.res, instrument_no=b.instrument_no,
                flags=(["booked_not_paid"] if b.date >= today - timedelta(days=60) else ["no_bank_match"]) + list(getattr(b.res, "flags", []) or []),
            ))

    # --- cross-source vendor rescue: unknown bank payee, but a bill row of same amount nearby already resolved ---
    for o in occs:
        if o.vendor_key:
            continue
        for b in occs:
            if b is o or not b.vendor_key:
                continue
            if abs(b.amount_paid - o.amount_paid) <= max(5.0, o.amount_paid * 0.02) and abs((b.date - o.date).days) <= 15 \
                    and set(b.sources) & BILL_SOURCES and set(o.sources) & PAYMENT_SOURCES and len(b.raw_row_ids) == 1:
                o.vendor_key, o.product, o.resolution, o.res = b.vendor_key, b.product, "cross", b.res
                o.sources += b.sources
                o.raw_row_ids += b.raw_row_ids
                o.invoice_no, o.period_from, o.period_to = b.invoice_no, b.period_from, b.period_to
                occs.remove(b)
                break

    # gateway-resolved amounts: if a gateway payment has no vendor, but same amount+day-of-month repeats, keep for question
    return sorted(occs, key=lambda o: o.date)
