"""Orchestrates: file rows -> RawRow -> occurrences -> streams -> status -> questions, with DB persistence.
User edits live in Stream.user_fields and are never overwritten by a re-run."""
from __future__ import annotations
import hashlib
import logging
import threading
from datetime import date, datetime
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, delete, text as sa_text
from sqlalchemy.orm import Session

from app import models as m
from app.engine.vendors import Catalog, get_catalog
from app.engine.normalize import clean_payee, detect_mode
from app.engine.dedupe import Row, build_occurrences
from app.engine.recurrence import build_streams, CYCLE_MONTHS
from app.engine.status import compute_status

log = logging.getLogger("ittracker.engine")

# one engine run per company at a time (in-process); on Postgres also a transaction-scoped advisory lock
_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def company_lock(company_id: int) -> threading.Lock:
    with _locks_guard:
        lk = _locks.get(company_id)
        if lk is None:
            lk = _locks[company_id] = threading.Lock()
        return lk


def today_ist() -> date:
    """The customer is in India; the server may not be."""
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


SOURCE_MAP = {"bank": "bank", "card": "card", "tally": "tally", "generic": "bank", "email": "email", "gst": "gst", "manual": "manual"}

GENERIC_VENDOR_OPTIONS = [
    {"key": "v:tally:TSS renewal", "label": "Tally TSS renewal"},
    {"key": "v:quickheal:Antivirus licence", "label": "Antivirus (Quick Heal / Seqrite / other)"},
    {"key": "v:microsoft365:Microsoft 365", "label": "Microsoft 365 / Office"},
    {"key": "v:google_workspace:Google Workspace", "label": "Google Workspace"},
    {"key": "v:solidworks:SolidWorks subscription", "label": "SolidWorks"},
    {"key": "v:autodesk:AutoCAD subscription", "label": "AutoCAD / Autodesk"},
    {"key": "v:sap_b1:SAP B1 maintenance", "label": "SAP B1 / ERP AMC"},
    {"key": "v:it_amc:IT support AMC", "label": "IT support / AMC (local vendor)"},
    {"key": "v:godaddy:Domain / hosting", "label": "Domain / hosting / website"},
    {"key": "hardware", "label": "Hardware / one-time purchase (not a subscription)"},
    {"key": "not_it", "label": "Not IT at all — hide it"},
    {"key": "other", "label": "Other software (type the name)"},
]
CYCLE_OPTIONS = [
    {"key": "monthly", "label": "Monthly"}, {"key": "quarterly", "label": "Quarterly"},
    {"key": "half_yearly", "label": "Half-yearly"}, {"key": "yearly", "label": "Yearly"},
    {"key": "triennial", "label": "Every 3 years"}, {"key": "one_time", "label": "One-time, not repeating"},
]


def dedupe_key(source: str, d: date, amount: float, direction: str, desc: str) -> str:
    h = hashlib.sha1(f"{source}|{d.isoformat()}|{amount:.2f}|{direction}|{desc[:80].upper()}".encode()).hexdigest()
    return h[:40]


def ingest_rows(db: Session, company: m.Company, account: m.Account | None, batch: m.ImportBatch,
                rows: list[dict], source_kind: str, is_personal: bool = False) -> tuple[int, int]:
    source = SOURCE_MAP.get(source_kind, "bank")
    existing = {k for (k,) in db.execute(select(m.RawRow.dedupe_key).where(m.RawRow.company_id == company.id)).all()}
    added, skipped = 0, 0
    seen_in_file: dict[str, int] = {}
    for r in rows:
        base = dedupe_key(source, r["date"], r["amount"], r["direction"], r["raw_description"])
        n = seen_in_file.get(base, 0)
        seen_in_file[base] = n + 1
        key = base if n == 0 else f"{base}#{n}"   # two identical lines in one file are two payments (rule 2.47)
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        desc = r["raw_description"]
        db.add(m.RawRow(
            company_id=company.id, account_id=account.id if account else None, batch_id=batch.id, source=source,
            date=r["date"], amount=float(r["amount"]), direction=r["direction"], currency=r.get("currency") or "INR",
            fx_amount=r.get("fx_amount"), raw_description=desc, payee_clean=clean_payee(desc)[:200],
            payment_mode=detect_mode(desc) if source in ("bank", "card") else ("cash" if source == "manual" else None),
            invoice_no=(r.get("ref") if source in ("tally", "email", "gst") else None),
            period_from=r.get("period_from"), period_to=r.get("period_to"), taxable=r.get("taxable"), gst=r.get("gst"),
            ledger=r.get("ledger"), is_personal=is_personal, dedupe_key=key,
        ))
        added += 1
    db.flush()
    return added, skipped


def _vendor_ids(db: Session) -> tuple[dict[str, int], dict[int, str]]:
    rows = db.execute(select(m.Vendor.key, m.Vendor.id)).all()
    return {k: i for k, i in rows}, {i: k for k, i in rows}


def _load_learned(db: Session, catalog: Catalog):
    id2key = _vendor_ids(db)[1]
    rows = db.execute(select(m.VendorAlias)).scalars().all()
    catalog.load_learned([(a.company_id or 0, a.pattern, a.kind, id2key.get(a.vendor_id, ""), a.product) for a in rows if a.company_id])


def run_engine(db: Session, company_id: int, today: date | None = None) -> dict:
    with company_lock(company_id):
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            db.execute(sa_text("SELECT pg_advisory_xact_lock(:cid)"), {"cid": company_id})
        summary = _run_engine(db, company_id, today)
    log.info("engine run company_id=%s occurrences=%s streams=%s questions_open=%s", company_id,
             summary["occurrences"], summary["streams"], summary["questions_open"])
    return summary


def _run_engine(db: Session, company_id: int, today: date | None = None) -> dict:
    today = today or today_ist()
    catalog = get_catalog()
    _load_learned(db, catalog)
    key2id, _ = _vendor_ids(db)
    accounts = {a.id: a for a in db.execute(select(m.Account).where(m.Account.company_id == company_id)).scalars()}
    raw = db.execute(select(m.RawRow).where(m.RawRow.company_id == company_id)).scalars().all()

    rows: list[Row] = []
    for r in raw:
        res = catalog.resolve(r.payee_clean, r.amount, r.raw_description, r.ledger or "", company_id)
        acc = accounts.get(r.account_id)
        rows.append(Row(
            id=r.id, source=r.source if r.source != "generic" else "bank", date=r.date, amount=r.amount, direction=r.direction,
            payee_clean=r.payee_clean, raw_description=r.raw_description, currency=r.currency, fx_amount=r.fx_amount,
            payment_mode=r.payment_mode, invoice_no=r.invoice_no, period_from=r.period_from, period_to=r.period_to,
            taxable=r.taxable, gst=r.gst, ledger=r.ledger, is_personal=r.is_personal, account_id=r.account_id,
            account_label=(acc.label if acc else None), res=res,
        ))
    occs = build_occurrences(rows, catalog)
    results = build_streams(occs, catalog, today)

    # ---- persist streams (preserve user fields) ----
    existing = {s.stream_key: s for s in db.execute(select(m.Stream).where(m.Stream.company_id == company_id)).scalars()}
    seen_keys: set[str] = set()
    db.execute(delete(m.Occurrence).where(m.Occurrence.company_id == company_id))
    db.flush()
    summary = {"occurrences": len(occs), "streams": 0, "auto_accepted": 0, "needs_confirm": 0, "unclassified": 0}

    for sr in results:
        seen_keys.add(sr.key)
        st = existing.get(sr.key)
        if st is None:
            st = m.Stream(company_id=company_id, stream_key=sr.key)
            db.add(st)
        uf = dict(st.user_fields or {})
        # a next_due the user typed is only valid until the next real payment arrives
        if "next_due" in uf and uf.get("next_due_basis") and sr.last_paid_date and sr.last_paid_date.isoformat() > uf["next_due_basis"]:
            uf.pop("next_due", None); uf.pop("next_due_basis", None)
            st.user_fields = uf
        engine_vals = dict(
            vendor_id=key2id.get(sr.vendor_key) if sr.vendor_key else None, vendor_name=(sr.vendor_name or "")[:120], payee_name=(sr.payee_name or "")[:200],
            product=sr.product, category=sr.category, stream_type=sr.stream_type, cycle=sr.cycle, cycle_months=sr.cycle_months,
            expected_amount=sr.expected_amount, avg_amount=sr.avg_amount, last_amount=sr.last_amount, currency=sr.currency,
            first_seen=sr.first_seen, last_paid_date=sr.last_paid_date, next_due=sr.next_due, anchor_day=sr.anchor_day,
            confidence=sr.confidence, auto_renew=sr.auto_renew, paid_from=sr.paid_from, flags=sr.flags,
            amount_history=sr.amount_history, occurrences_count=len(sr.occurrences), sources=sr.sources,
            extra={k: getattr(sr, k) for k in ("rcm_gst", "quantity", "unit_price", "change_note", "supplier_history") if getattr(sr, k, None) not in (None, [])},
        )
        for k, v in engine_vals.items():
            if k in uf:
                continue
            setattr(st, k, v)
        # user-set cycle changes next_due maths
        if "cycle" in uf and st.last_paid_date and st.cycle_months and "next_due" not in uf:
            st.next_due = st.last_paid_date + relativedelta(months=int(st.cycle_months))
        if not st.pay_url and sr.vendor_key and catalog.vendor(sr.vendor_key) and "pay_url" not in uf:
            st.pay_url = catalog.vendor(sr.vendor_key).pay_url
        st.status = compute_status(
            stream_type=st.stream_type, cycle=st.cycle, cycle_months=st.cycle_months, next_due=st.next_due,
            last_paid_date=st.last_paid_date, auto_renew=st.auto_renew, confidence=st.confidence,
            is_user_modified=st.is_user_modified, dismissed=st.dismissed, cancelled=(uf.get("status") == "cancelled"), today=today,
        )
        if "status" in uf and uf["status"] not in ("cancelled",):
            st.status = uf["status"] if uf["status"] in ("active", "stopped", "one_time") else st.status
        db.flush()
        for o in sr.occurrences:
            db.add(m.Occurrence(
                company_id=company_id, vendor_id=key2id.get(o.vendor_key) if o.vendor_key else None, payee_clean=o.payee_clean,
                product=o.product, date=o.date, amount_paid=o.amount_paid, amount_gross=o.amount_gross, taxable=o.taxable,
                gst=o.gst, tds=o.tds, fees=o.fees, currency=o.currency, fx_amount=o.fx_amount, payment_mode=o.payment_mode,
                auto_renew=o.auto_renew, invoice_no=o.invoice_no, period_from=o.period_from, period_to=o.period_to,
                is_personal=o.is_personal, unpaid=o.unpaid, sources=o.sources, raw_row_ids=o.raw_row_ids,
                raw_description=o.raw_description, resolution=o.resolution, stream_id=st.id, manual=("manual" in o.sources),
            ))
        summary["streams"] += 1
        if st.status == "needs_confirm":
            summary["needs_confirm"] += 1
        elif st.status in ("active", "due_soon", "overdue", "charge_missed"):
            summary["auto_accepted"] += 1
        if not st.vendor_id:
            summary["unclassified"] += 1

    # streams the engine no longer produces: keep manual / user-modified, drop the rest
    for key, st in existing.items():
        if key in seen_keys or key.startswith("manual|"):
            continue
        if st.is_user_modified:
            continue
        db.execute(delete(m.Question).where(m.Question.stream_id == st.id, m.Question.answered == False))  # noqa: E712
        for q in db.execute(select(m.Question).where(m.Question.stream_id == st.id)).scalars():
            q.stream_id = None
        db.flush()
        db.delete(st)
    # manual streams: refresh status
    for st in db.execute(select(m.Stream).where(m.Stream.company_id == company_id, m.Stream.stream_key.like("manual|%"))).scalars():
        st.status = compute_status(stream_type=st.stream_type, cycle=st.cycle, cycle_months=st.cycle_months, next_due=st.next_due,
                                   last_paid_date=st.last_paid_date, auto_renew=st.auto_renew, confidence=100,
                                   is_user_modified=True, dismissed=st.dismissed, cancelled=(st.user_fields or {}).get("status") == "cancelled", today=today)
        summary["streams"] += 1
    db.flush()

    # ---- questions ----
    summary["questions_open"] = _make_questions(db, company_id, results, catalog, today)
    summary["ran_at"] = datetime.utcnow().isoformat()
    db.commit()
    return summary


def _fmt_money(x: float) -> str:
    return "₹" + f"{x:,.0f}"


def _make_questions(db: Session, company_id: int, results, catalog: Catalog, today: date) -> int:
    streams = {s.stream_key: s for s in db.execute(select(m.Stream).where(m.Stream.company_id == company_id)).scalars()}
    existing = {q.key: q for q in db.execute(select(m.Question).where(m.Question.company_id == company_id)).scalars()}
    wanted: dict[str, dict] = {}
    for sr in results:
        st = streams.get(sr.key)
        if not st or st.is_user_modified or st.dismissed:
            continue
        dates = [o.date.strftime("%-d %b %Y") for o in sr.occurrences][-6:]
        amt = sr.expected_amount or 0
        yearly_value = amt * (12 / sr.cycle_months) if sr.cycle_months else amt
        ctx = {"payee": sr.payee_name, "amount": amt, "dates": dates, "cycle_guess": sr.cycle, "sources": sr.sources}
        # 1. unknown vendor
        res0 = sr.occurrences[0].res if sr.occurrences else None
        # 1b. known reseller, product unknown, big bill -> which product(s) is this? (maybe several in one bill)
        fp = catalog.fingerprint(amt) if amt else None
        is_bundle = getattr(sr, "needs_bundle", False) or (
            sr.needs_vendor and res0 is not None and res0.is_reseller and not sr.product and amt >= 5000 and bool(res0.candidates or fp))
        if is_bundle and res0 is not None:
            key = f"bundle|{sr.payee_name}"
            opts = []
            for c in res0.candidates:
                v = catalog.vendor(c)
                opts.append({"key": f"v:{c}:", "label": v.name if v else c})
            if fp and fp.get("vendor") and not any(o["key"].startswith(f"v:{fp['vendor']}:") for o in opts):
                v = catalog.vendor(fp["vendor"])
                opts.append({"key": f"v:{fp['vendor']}:{fp.get('product') or ''}", "label": f"{v.name if v else fp['vendor']} ({fp.get('product') or 'list price match'})"})
            opts.append({"key": "split", "label": "Split into several"})
            wanted[key] = dict(kind="bundle", prompt=f"{_fmt_money(amt)} paid to reseller \"{sr.payee_name}\" on {dates[-1]} — which product is this? (or split it if the bill covers several)",
                               context={**ctx, "candidates": list(res0.candidates)}, options=opts, stream_id=st.id)
            continue
        if sr.needs_vendor:
            looks_it = res0.looks_it if res0 else False
            if yearly_value >= 5000 or looks_it or len(sr.occurrences) >= 2:
                key = f"vendor|{sr.payee_name}"
                opts = list(GENERIC_VENDOR_OPTIONS)
                if sr.occurrences[0].res and sr.occurrences[0].res.candidates:
                    cand = [{"key": f"v:{c}:", "label": catalog.vendor(c).name if catalog.vendor(c) else c} for c in sr.occurrences[0].res.candidates]
                    opts = cand + opts
                when = f"on {len(dates)} dates ({dates[0]} … {dates[-1]})" if len(dates) > 1 else f"on {dates[0]}"
                wanted[key] = dict(kind="vendor", prompt=f"{_fmt_money(amt)} paid to \"{sr.payee_name}\" {when} — what is this?",
                                   context=ctx, options=opts, stream_id=st.id)
            continue
        # 2. seen once, vendor known but cycle guessed from default
        if len(sr.occurrences) == 1 and sr.stream_type == "subscription" and "cycle_from_invoice" not in sr.flags and yearly_value >= 5000 \
                and not (sr.occurrences[0].res and sr.occurrences[0].res.method == "fingerprint"):
            key = f"cycle|{sr.key}"
            wanted[key] = dict(kind="cycle", prompt=f"{sr.vendor_name} {_fmt_money(amt)} seen once on {dates[0]}. How often is this paid?",
                               context=ctx, options=CYCLE_OPTIONS, stream_id=st.id)
        # 3. stopped
        if st.status in ("stopped", "amc_lapsed"):
            last_paid_txt = sr.last_paid_date.strftime("%-d %b %Y") if sr.last_paid_date else "a while"
            key = f"stopped|{sr.key}"
            wanted[key] = dict(kind="stopped", prompt=f"{sr.vendor_name} — no payment since {last_paid_txt}. Cancelled, or forgot to pay?",
                               context=ctx, options=[{"key": "cancelled", "label": "Cancelled / stopped using"},
                                                     {"key": "still_active", "label": "Still using — remind me"},
                                                     {"key": "paid_elsewhere", "label": "Paid from another account (add it later)"}],
                               stream_id=st.id)
    open_count = 0
    for key, spec in wanted.items():
        q = existing.get(key)
        if q is None:
            db.add(m.Question(company_id=company_id, key=key, **spec))
            open_count += 1
        else:
            if not q.answered:
                q.prompt, q.context, q.options, q.stream_id = spec["prompt"], spec["context"], spec["options"], spec["stream_id"]
                open_count += 1
    # close questions whose subject disappeared
    for key, q in existing.items():
        if key not in wanted and not q.answered:
            db.delete(q)
    db.flush()
    return open_count


def answer_question(db: Session, q: m.Question, choice: str, text: str | None = None, items: list[dict] | None = None,
                    run: bool = True) -> m.Stream | None:
    """Apply one answer. `run=False` defers the engine re-run (bulk answers run it once at the end)."""
    catalog = get_catalog()
    key2id, _ = _vendor_ids(db)
    st = db.get(m.Stream, q.stream_id) if q.stream_id else None
    payee = (q.context or {}).get("payee") or (st.payee_name if st else None)
    if q.kind == "bundle":
        if choice == "split":
            for it in items or []:
                vk = it.get("vendor_key") or ""
                name = it.get("product") or (catalog.vendor(vk).name if catalog.vendor(vk) else vk) or "Software"
                vinfo = catalog.vendor(vk)
                vname = vinfo.name if vinfo else (it.get("vendor_name") or name)
                months = CYCLE_MONTHS.get((vinfo.default_cycle if vinfo else "yearly") or "yearly")
                last = st.last_paid_date if st else None
                ms = m.Stream(company_id=q.company_id, stream_key="manual|pending", vendor_id=key2id.get(vk), vendor_name=vname[:120],
                              payee_name=payee, product=it.get("product"), category=(vinfo.category if vinfo else "other"),
                              stream_type="subscription", cycle=(vinfo.default_cycle if vinfo and months else "yearly") if months else "irregular",
                              cycle_months=months, expected_amount=float(it.get("amount") or 0), avg_amount=float(it.get("amount") or 0),
                              last_amount=float(it.get("amount") or 0), first_seen=last, last_paid_date=last,
                              next_due=(last + relativedelta(months=int(months))) if last and months else None, confidence=100,
                              paid_from=st.paid_from if st else None, is_user_modified=True,
                              user_fields={"manual": True, "split_from": st.id if st else None}, sources=["manual"],
                              occurrences_count=1 if last else 0, flags=["split_from_bundle"])
                db.add(ms)
                db.flush()
                ms.stream_key = f"manual|{ms.id}"
                ms.status = compute_status(stream_type=ms.stream_type, cycle=ms.cycle, cycle_months=ms.cycle_months, next_due=ms.next_due,
                                           last_paid_date=ms.last_paid_date, auto_renew=False, confidence=100, is_user_modified=True,
                                           dismissed=False, cancelled=False)
            if st:
                st.dismissed, st.is_user_modified = True, True
                st.user_fields = {**(st.user_fields or {}), "dismissed": True, "split": True}
                st.status = "dismissed"
            q.answered, q.answer = True, "split"
            db.commit()
            return st
        if choice.startswith("v:"):
            _, vk, product = choice.split(":", 2)
            vk = vk if vk in key2id else _ensure_vendor(db, vk, catalog, key2id)
            _learn(db, q.company_id, payee, key2id[vk], product or (text or None))
        q.answered, q.answer = True, choice if not text else f"{choice}:{text}"
        db.flush()
        if run:
            run_engine(db, q.company_id)
        else:
            db.commit()
        return db.get(m.Stream, q.stream_id) if q.stream_id else None
    if q.kind == "vendor":
        if choice == "not_it":
            _learn(db, q.company_id, payee, key2id["not_it"], None)
        elif choice == "hardware":
            _learn(db, q.company_id, payee, key2id["hardware"], "Hardware / one-time purchase")
        elif choice == "other":
            name = (text or "Other software").strip()
            vk = _ensure_vendor(db, name, catalog, key2id)
            _learn(db, q.company_id, payee, key2id[vk], name)
        elif choice.startswith("v:"):
            _, vk, product = choice.split(":", 2)
            vk = vk if vk in key2id else _ensure_vendor(db, vk, catalog, key2id)
            _learn(db, q.company_id, payee, key2id[vk], product or None)
        q.answered, q.answer = True, choice if not text else f"{choice}:{text}"
        db.flush()
        if run:
            run_engine(db, q.company_id)
        else:
            db.commit()
        return db.get(m.Stream, q.stream_id) if q.stream_id else None
    if q.kind == "cycle" and st:
        uf = dict(st.user_fields or {})
        if choice == "one_time":
            st.stream_type, st.cycle, st.cycle_months, st.next_due = "one_time", "irregular", None, None
            uf.update(stream_type="one_time", cycle="irregular", cycle_months=None, next_due=None)
        else:
            st.cycle, st.cycle_months = choice, CYCLE_MONTHS.get(choice)
            if st.last_paid_date and st.cycle_months:
                st.next_due = st.last_paid_date + relativedelta(months=int(st.cycle_months))
            uf.update(cycle=st.cycle, cycle_months=st.cycle_months)
        st.user_fields, st.is_user_modified, st.confidence = uf, True, 100
        st.status = compute_status(stream_type=st.stream_type, cycle=st.cycle, cycle_months=st.cycle_months, next_due=st.next_due,
                                   last_paid_date=st.last_paid_date, auto_renew=st.auto_renew, confidence=100, is_user_modified=True,
                                   dismissed=st.dismissed, cancelled=False)
        q.answered, q.answer = True, choice
        db.commit()
        return st
    if q.kind == "stopped" and st:
        uf = dict(st.user_fields or {})
        if choice == "cancelled":
            uf["status"] = "cancelled"
            st.status = "cancelled"
        elif choice == "still_active":
            st.next_due = today_ist() + relativedelta(days=7)
            uf["next_due"] = st.next_due.isoformat()
            st.status = "due_soon"
            st.flags = list(st.flags or []) + ["user_says_active"]
        else:
            st.flags = list(st.flags or []) + ["paid_elsewhere"]
            uf["status"] = "active"
            st.status = "active"
        st.user_fields, st.is_user_modified = uf, True
        q.answered, q.answer = True, choice
        db.commit()
        return st
    q.answered, q.answer = True, choice
    db.commit()
    return st


def _learn(db: Session, company_id: int, payee: str | None, vendor_id: int, product: str | None):
    if not payee:
        return
    import re as _re
    db.add(m.VendorAlias(vendor_id=vendor_id, pattern=f"^{_re.escape(payee)}$", kind="regex", product=product, company_id=company_id))
    db.flush()


def _ensure_vendor(db: Session, name: str, catalog: Catalog, key2id: dict) -> str:
    """Create a custom vendor for a name the user typed (kept in DB; catalog gets it via learned alias flow)."""
    import re
    key = "custom_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]
    if key not in key2id:
        v = m.Vendor(key=key, name=name, category="other", default_cycle="yearly")
        db.add(v)
        db.flush()
        key2id[key] = v.id
        from app.engine.vendors import VendorInfo
        catalog.vendors[key] = VendorInfo(key=key, name=name, category="other", default_cycle="yearly")
    return key


def seed_vendors(db: Session):
    """Upsert the YAML catalogue into the vendors table (plus special pseudo-vendors)."""
    catalog = get_catalog()
    from app.engine.vendors import VendorInfo
    specials = {
        "not_it": VendorInfo(key="not_it", name="Not IT", category="other", exclude=True),
        "hardware": VendorInfo(key="hardware", name="Hardware / one-time", category="other", default_cycle="one_time"),
        "it_amc": VendorInfo(key="it_amc", name="IT support AMC (local vendor)", category="amc", default_cycle="yearly"),
    }
    for k, v in specials.items():
        catalog.vendors.setdefault(k, v)
    existing = {v.key: v for v in db.execute(select(m.Vendor)).scalars()}
    for key, info in catalog.vendors.items():
        v = existing.get(key)
        if v is None:
            v = m.Vendor(key=key)
            db.add(v)
        v.name, v.category, v.default_cycle, v.variable, v.prepaid = info.name, info.category, info.default_cycle, info.variable, info.prepaid
        v.currency, v.entity_type, v.is_reseller, v.sells, v.pay_url, v.exclude, v.intro_pricing = \
            info.currency, info.entity_type, info.is_reseller, info.sells, info.pay_url, info.exclude, info.intro_pricing
    # custom vendors created earlier need to be in the catalog too
    for key, v in existing.items():
        if key not in catalog.vendors:
            catalog.vendors[key] = VendorInfo(key=key, name=v.name, category=v.category, default_cycle=v.default_cycle, exclude=v.exclude)
    db.commit()
