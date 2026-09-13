"""Group occurrences into streams (one dashboard line each) and work out cycle, expected amount, next due, confidence."""
from __future__ import annotations
import math
import re
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median
from dateutil.relativedelta import relativedelta

from app.engine.dedupe import Occ
from app.engine.vendors import Catalog

CYCLES = {  # name: (nominal days, accept median range, per-gap tolerance, months)
    "monthly":     (30.4, (27, 34),    5,  1),
    "quarterly":   (91,   (84, 98),    10, 3),
    "half_yearly": (182,  (170, 195),  15, 6),
    "yearly":      (365,  (340, 395),  30, 12),
    "biennial":    (730,  (700, 760),  40, 24),
    "triennial":   (1096, (1060, 1130), 45, 36),
}
CYCLE_MONTHS = {k: v[3] for k, v in CYCLES.items()}
GRACE_DAYS = {"monthly": 7, "quarterly": 15, "half_yearly": 20, "yearly": 30, "biennial": 40, "triennial": 45}
DUE_SOON_DAYS = {"monthly": 5, "quarterly": 10, "half_yearly": 20, "yearly": 30, "biennial": 45, "triennial": 45}


@dataclass
class StreamResult:
    key: str
    vendor_key: str | None
    vendor_name: str
    payee_name: str | None
    product: str | None
    category: str
    stream_type: str            # subscription | amc | one_time | prepaid
    cycle: str                  # monthly ... | irregular | custom
    cycle_months: float | None
    expected_amount: float | None
    avg_amount: float | None
    last_amount: float | None
    currency: str
    first_seen: date | None
    last_paid_date: date | None
    next_due: date | None
    anchor_day: int | None
    confidence: int
    auto_renew: bool
    paid_from: str | None
    occurrences: list[Occ]
    flags: list[str] = field(default_factory=list)
    amount_history: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    missed_cycles: int = 0
    needs_vendor: bool = False   # unknown vendor -> question
    needs_bundle: bool = False   # known reseller, product unknown, big amount -> "split this bill?" question (2.28)
    supplier_history: list[str] = field(default_factory=list)   # [old payee, new payee] after a supplier switch (2.27)
    fy: str | None = None        # "2026-27": FY of the latest service period (2.41)
    rcm_gst: float | None = None # 18% IGST payable under reverse charge for foreign no-GST vendors (2.33)
    change_note: str | None = None   # "1,450 -> 1,740 on 3 Apr 2026" (2.16 / 2.17)
    quantity: int | None = None      # seats inferred from per-seat list prices (2.16)
    unit_price: float | None = None


def fy_of(d: date | None, start_month: int = 4) -> str | None:
    """Financial-year tag: 20 Mar 2026 -> "2025-26", 1 Apr 2026 -> "2026-27" (start_month=4)."""
    if not d:
        return None
    y = d.year if d.month >= start_month else d.year - 1
    return f"{y}-{(y + 1) % 100:02d}"


def snap_cycle(gaps: list[int]) -> tuple[str | None, float]:
    """Return (cycle, share of gaps that fit). Uses the median gap; gaps of 2x/3x nominal count as missed cycles."""
    if not gaps:
        return None, 0.0
    med = median(gaps)
    for name, (nominal, (lo, hi), tol, _) in CYCLES.items():
        if lo <= med <= hi:
            fit = 0
            for g in gaps:
                for mult in (1, 2, 3):
                    if abs(g - nominal * mult) <= tol * mult:
                        fit += 1
                        break
            return name, fit / len(gaps)
    return None, 0.0


def _cv(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    if m == 0:
        return 0.0
    var = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return (var ** 0.5) / m


def _same_amount(a: Occ, b: Occ, tol: float) -> bool:
    """Same amount band. When both sides carry the foreign-currency amount, compare that (2.31a): USD 54.99 is
    the same charge whether the bank converted it to Rs 4,612 or Rs 4,701."""
    if a.fx_amount and b.fx_amount:
        return abs(a.fx_amount - b.fx_amount) <= max(0.05, a.fx_amount * 0.03)
    ref = b.amount_gross
    return abs(a.amount_gross - ref) <= ref * tol


def _band_split(occs: list[Occ], tol: float) -> list[list[Occ]]:
    """Cluster by amount over time: an occurrence joins the band whose latest amount is within ±tol.
    A payment of ~2x / 3x a band's amount (±5%) is a catch-up for missed cycles (2.21) and joins that band
    without becoming its reference amount."""
    bands: list[list[Occ]] = []
    refs: list[Occ] = []        # per band: the last non-catch-up member
    for o in sorted(occs, key=lambda x: x.date):
        placed = False
        for i, b in enumerate(bands):
            if _same_amount(o, refs[i], tol):
                b.append(o)
                refs[i] = o
                placed = True
                break
        if not placed:
            for i, b in enumerate(bands):
                ref = refs[i].amount_gross
                if ref and any(abs(o.amount_gross - n * ref) <= n * ref * 0.05 for n in (2, 3)):
                    b.append(o)
                    placed = True
                    break
        if not placed:
            bands.append([o])
            refs.append(o)
    return bands


def _cluster_same_cycle(occs: list[Occ], within_days: int = 2) -> list[tuple[date, float, list[Occ]]]:
    """Several charges a day or two apart are one billing event (two seats billed separately, a payment split
    over two lines): returns (date of last charge, total amount, members) per event."""
    out: list[tuple[date, float, list[Occ]]] = []
    for o in sorted(occs, key=lambda x: x.date):
        if out and (o.date - out[-1][0]).days <= within_days:
            d, total, members = out[-1]
            out[-1] = (o.date, round(total + o.amount_gross, 2), members + [o])
        else:
            out.append((o.date, o.amount_gross, [o]))
    return out


def _clamp_day(d: date, day: int) -> date:
    """Same month as d, on `day` clamped to the month's length (anchor 31 -> 30 Jun, 28 Feb, 31 Jul)."""
    return d.replace(day=min(day, monthrange(d.year, d.month)[1]))


def _merge_step_changes(bands: list[list[Occ]]) -> list[list[Occ]]:
    """Bands that don't overlap in time and differ by a step (seat change / price hike, ratio 0.5–2.5) become one stream."""
    bands = sorted(bands, key=lambda b: b[0].date)
    merged: list[list[Occ]] = []
    for b in bands:
        if merged:
            prev = merged[-1]
            ratio = b[0].amount_gross / prev[-1].amount_gross if prev[-1].amount_gross else 0
            if b[0].date > prev[-1].date and 0.5 <= ratio <= 2.5:
                merged[-1] = prev + b
                continue
        merged.append(b)
    return merged


def build_streams(occs: list[Occ], catalog: Catalog, today: date | None = None, fy_start_month: int = 4) -> list[StreamResult]:
    today = today or date.today()
    # ---- group by vendor (or cleaned payee) + currency ----
    groups: dict[tuple, list[Occ]] = {}
    for o in occs:
        o.fy = fy_of(o.period_from or o.date, fy_start_month)
        gkey = (o.vendor_key or f"payee:{o.payee_clean}", o.currency)
        groups.setdefault(gkey, []).append(o)

    streams: list[StreamResult] = []
    for (gk, currency), members in groups.items():
        vinfo = catalog.vendor(members[0].vendor_key)
        variable = bool(vinfo and vinfo.variable)
        prepaid = bool(vinfo and vinfo.prepaid)

        # Unknown payee with no IT-ish words: only keep it if it behaves like a subscription
        # (stable amount and a regular gap). Raw-material suppliers, contractors etc. are dropped here.
        if vinfo is None:
            looks_it = any(o.res and (o.res.looks_it or o.res.is_gateway or o.res.is_reseller) for o in members)
            amts = [o.amount_gross for o in members]
            ds = sorted(o.date for o in members)
            gaps = [(ds[i] - ds[i - 1]).days for i in range(1, len(ds))]
            regular = bool(gaps) and snap_cycle(gaps)[0] is not None and _cv(amts) <= 0.15
            if not looks_it and not regular:
                continue

        # split by product when products are known and differ
        by_product: dict[str, list[Occ]] = {}
        for o in members:
            by_product.setdefault((o.product if (o.product and not o.product_soft) else "*"), []).append(o)
        # a "*" product bucket merges into the single named product if there is exactly one
        named = [k for k in by_product if k != "*"]
        if "*" in by_product and len(named) == 1:
            by_product[named[0]] += by_product.pop("*")

        for product, plist in by_product.items():
            if variable or prepaid:
                bands = [sorted(plist, key=lambda x: x.date)]
            else:
                bands = _merge_step_changes(_band_split(plist, 0.12))
                # perpetual licence + AMC (2.11): a lone big payment >= 3x the repeating band, occurring first
                repeating = [b for b in bands if len(b) >= 2]
                if repeating:
                    small = min(sum(o.amount_gross for o in b) / len(b) for b in repeating)
                    new_bands = []
                    for b in bands:
                        need = 2 if _LICENCE_RX.search(b[0].raw_description or "") else 3
                        if len(b) == 1 and b[0].amount_gross >= need * small and b[0].date <= min(o.date for r in repeating for o in r):
                            streams.append(_one_time(b[0], vinfo, currency, catalog, gk))
                        else:
                            new_bands.append(b)
                    bands = new_bands
            for b in bands:
                streams.append(_stream_from_band(b, vinfo, currency, catalog, gk, product, variable, prepaid, today, fy_start_month))
    return _merge_supplier_switch(streams)


def _cycle_days(st: StreamResult) -> float:
    return (st.cycle_months or 1) * 30.4


def _merge_supplier_switch(streams: list[StreamResult]) -> list[StreamResult]:
    """2.27: the same product bought first via one payee (reseller yearly) and then via another (direct monthly).
    Old stream's last payment falls within one cycle (+30 days) of the new stream's first payment and the
    monthly-equivalents agree within +-25% -> one stream keyed on the newer band, with a supplier note."""
    by_vendor: dict[tuple, list[StreamResult]] = {}
    for st in streams:
        if st.vendor_key and st.stream_type in ("subscription", "amc") and st.cycle_months:
            by_vendor.setdefault((st.vendor_key, st.currency), []).append(st)
    drop: set[int] = set()
    for group in by_vendor.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda s: (s.first_seen or date.min))
        for i, new in enumerate(group):
            if id(new) in drop or not new.first_seen:
                continue
            for old in group[:i]:
                if id(old) in drop or not old.last_paid_date or not old.first_seen:
                    continue
                if (old.payee_name or "") == (new.payee_name or "") or old.last_paid_date > new.first_seen:
                    continue
                allowed = max(_cycle_days(old), _cycle_days(new)) + 30
                if (new.first_seen - old.last_paid_date).days > allowed:
                    continue
                meq_old = (old.expected_amount or 0) / (old.cycle_months or 1)
                meq_new = (new.expected_amount or 0) / (new.cycle_months or 1)
                if not meq_old or abs(meq_new - meq_old) > meq_old * 0.25:
                    continue
                new.occurrences = sorted(old.occurrences + new.occurrences, key=lambda o: o.date)
                new.amount_history = old.amount_history + new.amount_history
                new.first_seen = old.first_seen
                new.sources = sorted(set(old.sources) | set(new.sources))
                new.supplier_history = (old.supplier_history or [old.payee_name or ""]) + [new.payee_name or ""]
                if "supplier_changed" not in new.flags:
                    new.flags.append("supplier_changed")
                drop.add(id(old))
                break
    return [s for s in streams if id(s) not in drop]


_LICENCE_RX = re.compile(r"LICEN[CS]E|PURCHASE|NEW LIC|PERPETUAL", re.I)


def _vendor_name(vinfo, occ: Occ) -> str:
    if vinfo:
        return vinfo.name
    return occ.payee_clean.title() if occ.payee_clean else "Unknown"


def _one_time(o: Occ, vinfo, currency, catalog, gk) -> StreamResult:
    return StreamResult(
        key=f"{gk}|one_time|{o.date.isoformat()}|{int(o.amount_gross)}", vendor_key=o.vendor_key,
        vendor_name=_vendor_name(vinfo, o), payee_name=o.payee_clean, product=o.product or "Licence purchase (one-time)",
        category=vinfo.category if vinfo else "other", stream_type="one_time", cycle="irregular", cycle_months=None,
        expected_amount=o.amount_gross, avg_amount=o.amount_gross, last_amount=o.amount_gross, currency=currency,
        first_seen=o.date, last_paid_date=o.date, next_due=None, anchor_day=None, confidence=80,
        auto_renew=False, paid_from=o.account_label, occurrences=[o], flags=["one_time_licence"], sources=sorted(set(o.sources)),
    )


def _expand_catch_ups(dates: list[date], amounts: list[float], variable: bool) -> tuple[list[date], list[float], dict[int, int]]:
    """2.21 anywhere in the history: an event of ~N x the typical amount (N = 2 or 3, +-5%) after a gap of ~N cycles
    is N payments made together. Returns virtual (dates, amounts) with the event split into N evenly spaced
    payments of amount/N, plus {event index: N}. Cycle detection, fit, stability and price-change checks use the
    virtual series; the real series is kept for expected/last amounts."""
    catch: dict[int, int] = {}
    if variable or len(amounts) < 3:
        return list(dates), list(amounts), catch
    base = median(amounts)
    v_dates: list[date] = []
    v_amounts: list[float] = []
    for i, (d, a) in enumerate(zip(dates, amounts)):
        n = int(round(a / base)) if base else 1
        if i > 0 and n in (2, 3) and abs(a - n * base) <= base * 0.05:
            gap = (d - dates[i - 1]).days
            step = gap / n
            for k in range(n - 1, -1, -1):
                v_dates.append(d - timedelta(days=int(round(step * k))))
                v_amounts.append(round(a / n, 2))
            catch[i] = n
        else:
            v_dates.append(d)
            v_amounts.append(a)
    return v_dates, v_amounts, catch


def _ref_ordinal(d: date) -> int:
    """Day-of-year on a non-leap reference year (29 Feb -> 28 Feb) so a leap year does not shift the anchor."""
    return d.replace(year=2001, day=min(d.day, 28) if d.month == 2 else d.day).toordinal()


def _snap_anchor(next_due: date, dates: list[date], cycle: str) -> tuple[date, int | None]:
    """2.19: with >= 3 payments, snap next_due to the median day-of-year (yearly) or day-of-month (others) of the
    last three, when the snap moves it by <= 45 days."""
    last3 = dates[-3:]
    if cycle == "yearly":
        med = sorted(last3, key=_ref_ordinal)[1]
        try:
            cand = date(next_due.year, med.month, med.day)
        except ValueError:
            cand = date(next_due.year, med.month, 28)
        anchor = None
    else:
        anchor = int(median([d.day for d in last3]))
        cand = _clamp_day(next_due, anchor)
    if abs((cand - next_due).days) <= 45:
        return cand, anchor
    return next_due, None


def _stream_from_band(band: list[Occ], vinfo, currency, catalog, gk, product, variable, prepaid, today, fy_start_month: int = 4) -> StreamResult:
    band = sorted(band, key=lambda x: x.date)
    paid = [o for o in band if not o.unpaid]
    events = _cluster_same_cycle(paid or band)
    dates = [e[0] for e in events]
    amounts = [e[1] for e in events]
    fx_amounts = [sum(o.fx_amount or 0 for o in e[2]) for e in events] if all(o.fx_amount for e in events for o in e[2]) else []
    raw_gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    raw_gaps = [g for g in raw_gaps if g > 0]
    # catch-up payments anywhere in the history count as N payments for cycle / fit / stability (2.21)
    v_dates, v_amounts, catch = _expand_catch_ups(dates, amounts, variable or prepaid)
    gaps = [(v_dates[i] - v_dates[i - 1]).days for i in range(1, len(v_dates))]
    gaps = [g for g in gaps if g > 0]
    if any(len(e[2]) > 1 for e in events):
        flags_multi = [f"{max(len(e[2]) for e in events)}_charges_per_cycle"]
    else:
        flags_multi = []
    flags: list[str] = list(flags_multi)
    for n in sorted(set(catch.values())):
        flags.append(f"catch_up_{n}_cycles")
    first = band[0]
    last_paid = paid[-1] if paid else None

    # fingerprint / vendor defaults
    default_cycle = (first.res.suggested_cycle if first.res and first.res.suggested_cycle else (vinfo.default_cycle if vinfo else None))
    if default_cycle == "one_time":
        return _one_time(first, vinfo, currency, catalog, gk)

    # ---- cycle ----
    cycle, fit = (None, 0.0)
    stream_type = "subscription"
    if prepaid or (variable and _cv(gaps) > 0.5 and len(gaps) >= 2):
        stream_type = "prepaid"
        cycle = "irregular"
    elif len(gaps) >= 1:
        cycle, fit = snap_cycle(gaps)
        if cycle is None:
            if _cv(gaps) > 0.5 and all(a % 500 == 0 for a in amounts):
                stream_type, cycle = "prepaid", "irregular"
            else:
                cycle = "irregular"
    else:
        # single occurrence: invoice period / term text wins, else vendor default
        term = None
        if first.period_from and first.period_to:
            term = round(((first.period_to - first.period_from).days + 1) / 30.4)
        elif first.res and first.res.term_months:
            term = first.res.term_months
        if term:
            cycle = _cycle_from_months(term)
            if cycle == "custom":
                flags.append(f"custom_{term}m")
            flags.append("cycle_from_invoice")
        elif default_cycle:
            cycle = default_cycle
            flags.append("cycle_from_vendor_default")
        else:
            cycle = "irregular"
    months = CYCLE_MONTHS.get(cycle)
    if cycle == "custom" and flags and flags[0].startswith("custom_"):
        months = int(flags[0][7:-1])

    # AMC naming (2.11): small yearly payment to a CAD/ERP vendor whose product says AMC/maintenance
    if vinfo and vinfo.category in ("cad", "erp") and cycle == "yearly" and (product or "").upper().find("AMC") >= 0:
        stream_type = "amc"

    # ---- amounts (2.16/2.17: last amount predicts; variable: median of last 3; prepaid: 6-month run-rate) ----
    if stream_type == "prepaid":
        recent = [a for d, a in zip(dates, amounts) if d > today - relativedelta(months=6)]
        expected = round(sum(recent) / 6, 2)
        avg = sum(amounts) / len(amounts)
        if not recent:
            flags.append("no_topup_in_6_months")
    elif variable:
        recent = amounts[-3:]
        expected = median(recent)
        avg = sum(amounts) / len(amounts)
    else:
        expected = amounts[-1]
        avg = sum(amounts) / len(amounts)
        cmp = fx_amounts or v_amounts   # a USD charge whose INR value moves with the rate is not a price change (2.31)
        if len(cmp) >= 2 and (max(cmp) - min(cmp)) > min(cmp) * 0.05:
            flags.append("price_changed")
    # amount history with change notes ("+20%" on the occurrence where the amount stepped, 2.16/2.17)
    history: list[dict] = []
    change_note = None
    catch_members = {id(o) for i, n in catch.items() for o in events[i][2]}
    prev_amt: float | None = None
    prev_fx: float | None = None
    for o in band:
        item = {"date": o.date.isoformat(), "amount": o.amount_gross}
        if not variable and stream_type != "prepaid" and id(o) not in catch_members and not o.unpaid:
            same_fx = bool(o.fx_amount and prev_fx) and abs(o.fx_amount - prev_fx) <= max(0.05, prev_fx * 0.03)
            if prev_amt and not same_fx and abs(o.amount_gross - prev_amt) > prev_amt * 0.05:
                pct = (o.amount_gross - prev_amt) / prev_amt * 100
                item["change"] = f"{pct:+.0f}%"
                change_note = f"{prev_amt:,.0f} → {o.amount_gross:,.0f} on {o.date.strftime('%-d %b %Y')}"
            prev_amt, prev_fx = o.amount_gross, o.fx_amount
        history.append(item)
    if vinfo and vinfo.intro_pricing and len(amounts) == 1:
        flags.append("intro_price_renewal_may_be_higher")
    if any("tds" in f for o in band for f in o.flags):
        flags.append("tds_deducted")
    if vinfo and vinfo.entity_type == "foreign_no_gst":
        flags.append("rcm_gst_payable")
    if any(o.is_personal for o in band):
        flags.append("paid_from_personal")
        if all(o.is_personal for o in band) and not any(s in ("tally", "gst") for o in band for s in o.sources):
            flags.append("not_in_company_books")   # 2.36
    for fl in ("mixed_hardware_bill", "cheque_matched"):
        if any(fl in o.flags for o in band):
            flags.append(fl)

    # ---- next due (Step 7) ----
    anchor_day = None
    next_due = None
    if stream_type != "prepaid" and cycle not in ("irregular",) and months:
        if last_paid and last_paid.period_to:
            next_due = last_paid.period_to + timedelta(days=1)
        elif last_paid:
            next_due = last_paid.date + relativedelta(months=months)
            nominal = CYCLES[cycle][0] if cycle in CYCLES else months * 30.4
            # paid early (2.20): renewed > 15 days before the previous cycle ran out, no invoice period ->
            # next due = previous expected due + cycle, not payment date + cycle
            if months >= 3 and raw_gaps and len(dates) >= 2 and (nominal - raw_gaps[-1]) > 15 and (len(dates) - 1) not in catch:
                next_due = dates[-2] + relativedelta(months=2 * months)
                flags.append("paid_early")
            if cycle == "monthly" and len(dates) >= 2:
                anchor_day = int(median([d.day for d in dates[-3:]]))
                next_due = _clamp_day(next_due, anchor_day)
            elif cycle in ("quarterly", "half_yearly", "yearly") and len(dates) >= 3:
                next_due, anchor_day = _snap_anchor(next_due, dates, cycle)   # 2.19
        # catch-up on the LAST payment (2.21): the N-fold payment covers N cycles -> due date moves by N cycles
        if len(amounts) >= 3 and not variable and last_paid:
            prev = median(amounts[:-1])
            n = round(amounts[-1] / prev) if prev else 1
            nominal = CYCLES[cycle][0] if cycle in CYCLES else None
            gap_says_missed = bool(raw_gaps and nominal) and abs(raw_gaps[-1] - n * nominal) <= CYCLES[cycle][2] * n
            if n in (2, 3) and abs(amounts[-1] - n * prev) <= prev * 0.05:
                next_due = last_paid.date + relativedelta(months=months * n)
                expected = prev
                if f"catch_up_{n}_cycles" not in flags:
                    flags.append(f"catch_up_{n}_cycles")
                if "price_changed" in flags:
                    flags.remove("price_changed")
            elif n in (2, 3) and gap_says_missed and prev * n * 0.95 <= amounts[-1] <= prev * n * 1.5:
                # missed cycles paid together at a new (higher) price: catch-up AND price change (2.17 + 2.21)
                next_due = last_paid.date + relativedelta(months=months * n)
                expected = round(amounts[-1] / n, 2)
                flags.append(f"catch_up_{n}_cycles")
                if "price_changed" not in flags:
                    flags.append("price_changed")
    elif stream_type == "prepaid" and len(dates) >= 2:
        avg_gap = sum(raw_gaps) / len(raw_gaps) if raw_gaps else 0
        flags.append(f"topup_every_{int(avg_gap)}d")

    # ---- confidence (Step 5) ----
    n = len(paid)
    score = 30 if n >= 3 else (20 if n == 2 else 0)
    score += int(25 * fit) if gaps else (10 if "cycle_from_invoice" in flags else 0)
    if variable or stream_type == "prepaid":
        score += 15 if (n >= 2) else 0
    else:
        score += 15 if _cv(v_amounts) <= 0.03 or n == 1 else (8 if _cv(v_amounts) <= 0.15 else 0)
    if vinfo and cycle == vinfo.default_cycle:
        score += 15
    elif vinfo:
        score += 8
    if any(o.period_to or o.invoice_no for o in band):
        score += 10
    if any(o.auto_renew for o in band):
        score += 5
    if first.res and first.res.method == "gateway":
        score -= 10
    if first.res and first.res.method in ("fingerprint", "narration", "cross", "user"):
        score += 10
    if n <= 1 and "cycle_from_invoice" in flags and vinfo:
        score = max(score, 78)  # a known vendor whose invoice states the term: accept, no need to ask
    if n == 0 and any(o.unpaid for o in band):
        # booked in Tally but not paid yet: due now, count it in this month's cash-out
        next_due = band[-1].date + timedelta(days=15)
        flags.append("booked_not_paid")
        score = max(score, 78) if vinfo else min(score, 60)
    score = max(0, min(100, score))

    missed = 0
    if gaps and cycle in CYCLES:
        nominal = CYCLES[cycle][0]
        missed = sum(max(0, round(g / nominal) - 1) for g in gaps)

    # reseller bundle (2.28): known reseller, product unknown, big amount -> one stream, ask to split (not a vendor question)
    bundle = first.vendor_key is None and any(o.res and o.res.bundle for o in band)
    if bundle:
        flags.append("bundle_unknown_product")

    # stable key across re-runs: vendor + product + coarse amount bucket (quarter-decades, so ±30% stays in one bucket)
    band_id = int(round(math.log10(max(1.0, expected)) * 4)) if expected else 0
    key = f"{gk}|{product}|{band_id}"

    qty = catalog.infer_quantity(first.vendor_key, expected) if not variable and stream_type != "prepaid" else None
    fy_src = last_paid or band[-1]
    return StreamResult(
        key=key, vendor_key=first.vendor_key, vendor_name=_vendor_name(vinfo, first), payee_name=first.payee_clean,
        product=product if product != "*" else (first.product or None),
        category=vinfo.category if vinfo else ("other"), stream_type=stream_type, cycle=cycle,
        cycle_months=months, expected_amount=round(expected, 2), avg_amount=round(avg, 2), last_amount=amounts[-1],
        currency=currency, first_seen=first.date, last_paid_date=(last_paid.date if last_paid else None),
        next_due=next_due, anchor_day=anchor_day, confidence=score,
        auto_renew=any(o.auto_renew for o in band), paid_from=(last_paid.account_label if last_paid else first.account_label),
        occurrences=band, flags=flags, amount_history=history, sources=sorted({s for o in band for s in o.sources}),
        missed_cycles=missed, needs_vendor=(first.vendor_key is None and not bundle), needs_bundle=bundle,
        fy=fy_of(fy_src.period_from or fy_src.date, fy_start_month),
        rcm_gst=(round(expected * 0.18, 2) if vinfo and vinfo.entity_type == "foreign_no_gst" and expected else None),
        change_note=change_note, quantity=(qty[0] if qty else None), unit_price=(qty[1] if qty else None),
    )


def _cycle_from_months(months: int) -> str:
    for name, m in CYCLE_MONTHS.items():
        if abs(months - m) <= max(1, m * 0.15):
            return name
    return "custom"
