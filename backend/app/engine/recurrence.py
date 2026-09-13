"""Group occurrences into streams (one dashboard line each) and work out cycle, expected amount, next due, confidence."""
from __future__ import annotations
import math
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


def _band_split(occs: list[Occ], tol: float) -> list[list[Occ]]:
    """Cluster by amount over time: an occurrence joins the band whose latest amount is within ±tol."""
    bands: list[list[Occ]] = []
    for o in sorted(occs, key=lambda x: x.date):
        placed = False
        for b in bands:
            ref = b[-1].amount_gross
            if abs(o.amount_gross - ref) <= ref * tol:
                b.append(o)
                placed = True
                break
        if not placed:
            bands.append([o])
    return bands


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


def build_streams(occs: list[Occ], catalog: Catalog, today: date | None = None) -> list[StreamResult]:
    today = today or date.today()
    # ---- group by vendor (or cleaned payee) + currency ----
    groups: dict[tuple, list[Occ]] = {}
    for o in occs:
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
            looks_it = any(o.res and (o.res.looks_it or o.res.is_gateway) for o in members)
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
                        if len(b) == 1 and b[0].amount_gross >= 3 * small and b[0].date <= min(o.date for r in repeating for o in r):
                            streams.append(_one_time(b[0], vinfo, currency, catalog, gk))
                        else:
                            new_bands.append(b)
                    bands = new_bands
            for b in bands:
                streams.append(_stream_from_band(b, vinfo, currency, catalog, gk, product, variable, prepaid, today))
    return streams


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


def _stream_from_band(band: list[Occ], vinfo, currency, catalog, gk, product, variable, prepaid, today) -> StreamResult:
    band = sorted(band, key=lambda x: x.date)
    paid = [o for o in band if not o.unpaid]
    dates = [o.date for o in paid] or [o.date for o in band]
    amounts = [o.amount_gross for o in paid] or [o.amount_gross for o in band]
    gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    gaps = [g for g in gaps if g > 0]
    flags: list[str] = []
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
    if cycle == "irregular" and stream_type == "subscription" and len(gaps) == 0:
        # unknown single payment to an unknown payee
        pass
    months = CYCLE_MONTHS.get(cycle)
    if cycle == "custom" and flags and flags[0].startswith("custom_"):
        months = int(flags[0][7:-1])

    # AMC naming (2.11): small yearly payment to a CAD/ERP vendor whose product says AMC/maintenance
    if vinfo and vinfo.category in ("cad", "erp") and cycle == "yearly" and (product or "").upper().find("AMC") >= 0:
        stream_type = "amc"

    # ---- amounts (2.16/2.17: last amount predicts; variable: median of last 3) ----
    if variable or stream_type == "prepaid":
        recent = amounts[-3:]
        expected = median(recent)
        avg = sum(amounts) / len(amounts)
    else:
        expected = amounts[-1]
        avg = sum(amounts) / len(amounts)
        if len(amounts) >= 2 and (max(amounts) - min(amounts)) > min(amounts) * 0.05:
            flags.append("price_changed")
    history = [{"date": o.date.isoformat(), "amount": o.amount_gross} for o in band]
    if vinfo and vinfo.intro_pricing and len(amounts) == 1:
        flags.append("intro_price_renewal_may_be_higher")
    if any("tds" in f for o in band for f in o.flags):
        flags.append("tds_deducted")
    if vinfo and vinfo.entity_type == "foreign_no_gst":
        flags.append("rcm_gst_payable")
    if any(o.is_personal for o in band):
        flags.append("paid_from_personal")

    # ---- next due (Step 7) ----
    anchor_day = None
    next_due = None
    if stream_type != "prepaid" and cycle not in ("irregular",) and months:
        if last_paid and last_paid.period_to:
            next_due = last_paid.period_to + timedelta(days=1)
        elif last_paid:
            next_due = last_paid.date + relativedelta(months=months)
            if cycle == "monthly" and len(dates) >= 2:
                anchor_day = int(median([d.day for d in dates[-3:]]))
                try:
                    next_due = next_due.replace(day=min(anchor_day, 28))
                except ValueError:
                    pass
        # catch-up (2.21): if last amount is ~2x expected of previous ones, push due by an extra cycle
        if len(amounts) >= 3 and not variable:
            prev = median(amounts[:-1])
            n = round(amounts[-1] / prev) if prev else 1
            if n in (2, 3) and abs(amounts[-1] - n * prev) <= prev * 0.05:
                next_due = last_paid.date + relativedelta(months=months * n)
                expected = prev
                flags.append(f"catch_up_{n}_cycles")
                if "price_changed" in flags:
                    flags.remove("price_changed")
    elif stream_type == "prepaid" and len(dates) >= 2:
        avg_gap = sum(gaps) / len(gaps)
        flags.append(f"topup_every_{int(avg_gap)}d")

    # ---- confidence (Step 5) ----
    n = len(paid)
    score = 30 if n >= 3 else (20 if n == 2 else 0)
    score += int(25 * fit) if gaps else (10 if "cycle_from_invoice" in flags else 0)
    if variable or stream_type == "prepaid":
        score += 15 if (n >= 2) else 0
    else:
        score += 15 if _cv(amounts) <= 0.03 or n == 1 else (8 if _cv(amounts) <= 0.15 else 0)
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

    # stable key across re-runs: vendor + product + coarse amount bucket (quarter-decades, so ±30% stays in one bucket)
    band_id = int(round(math.log10(max(1.0, expected)) * 4)) if expected else 0
    key = f"{gk}|{product}|{band_id}"

    return StreamResult(
        key=key, vendor_key=first.vendor_key, vendor_name=_vendor_name(vinfo, first), payee_name=first.payee_clean,
        product=product if product != "*" else (first.product or None),
        category=vinfo.category if vinfo else ("other"), stream_type=stream_type, cycle=cycle,
        cycle_months=months, expected_amount=round(expected, 2), avg_amount=round(avg, 2), last_amount=amounts[-1],
        currency=currency, first_seen=first.date, last_paid_date=(last_paid.date if last_paid else None),
        next_due=next_due, anchor_day=anchor_day, confidence=score,
        auto_renew=any(o.auto_renew for o in band), paid_from=(last_paid.account_label if last_paid else first.account_label),
        occurrences=band, flags=flags, amount_history=history, sources=sorted({s for o in band for s in o.sources}),
        missed_cycles=missed, needs_vendor=(first.vendor_key is None),
    )


def _cycle_from_months(months: int) -> str:
    for name, m in CYCLE_MONTHS.items():
        if abs(months - m) <= max(1, m * 0.15):
            return name
    return "custom"
