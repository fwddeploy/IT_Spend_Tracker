from __future__ import annotations
from datetime import date, datetime, timedelta
from calendar import monthrange
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app import models as m
from app.api import schemas as S
from app.engine import runner
from app.engine.runner import today_ist
from app.engine.status import compute_status, due_dates_in_range, monthly_equivalent
from app.engine.recurrence import CYCLE_MONTHS
from app.parsers.tabular import parse_rows
from app.parsers.tally_xml import parse_tally_xml

import os
from fastapi import Request


def require_access_key(request: Request):
    """Pilot-grade gate: if APP_ACCESS_KEY is set, every API call must send it as X-Access-Key.
    (Real users/roles come later; this keeps a public demo box from being open to the world.)"""
    expected = os.environ.get("APP_ACCESS_KEY", "")
    if expected and request.headers.get("X-Access-Key", "") != expected:
        raise HTTPException(401, "Access key required")


router = APIRouter(prefix="/api", dependencies=[Depends(require_access_key)])


# ---------- helpers ----------
def _company(db: Session, company_id: int) -> m.Company:
    c = db.get(m.Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    return c


def _stream(db: Session, company_id: int, sid: int) -> m.Stream:
    st = db.get(m.Stream, sid)
    if not st or st.company_id != company_id:
        raise HTTPException(404, "Line item not found")
    return st


def stream_out(st: m.Stream) -> S.StreamOut:
    return S.StreamOut(
        id=st.id, vendor_name=st.vendor_name, payee_name=st.payee_name, product=st.product, category=st.category,
        stream_type=st.stream_type, cycle=st.cycle, cycle_months=st.cycle_months, expected_amount=st.expected_amount,
        avg_amount=st.avg_amount, monthly_equivalent=round(monthly_equivalent(st.expected_amount, st.cycle_months, st.stream_type), 2),
        currency=st.currency, last_paid_date=st.last_paid_date, next_due=st.next_due, anchor_day=st.anchor_day, status=st.status,
        confidence=st.confidence, auto_renew=st.auto_renew, paid_from=st.paid_from, owner_name=st.owner_name, pay_url=st.pay_url,
        reminder_on=st.reminder_on, notes=st.notes, is_user_modified=st.is_user_modified, occurrences_count=st.occurrences_count,
        sources=st.sources or [], first_seen=st.first_seen, flags=st.flags or [],
    )


def _recompute_status(st: m.Stream):
    st.status = compute_status(stream_type=st.stream_type, cycle=st.cycle, cycle_months=st.cycle_months, next_due=st.next_due,
                               last_paid_date=st.last_paid_date, auto_renew=st.auto_renew, confidence=st.confidence,
                               is_user_modified=st.is_user_modified, dismissed=st.dismissed,
                               cancelled=(st.user_fields or {}).get("status") == "cancelled")


LIVE = ("active", "due_soon", "overdue", "charge_missed")


# ---------- companies ----------
@router.get("/companies", response_model=list[S.CompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return db.execute(select(m.Company).order_by(m.Company.id)).scalars().all()


@router.post("/companies", response_model=S.CompanyOut)
def create_company(body: S.CompanyIn, db: Session = Depends(get_db)):
    c = m.Company(name=body.name.strip(), gstin=body.gstin, fy_start_month=body.fy_start_month)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/companies/{company_id}", response_model=S.CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db)):
    return _company(db, company_id)


@router.get("/companies/{company_id}/accounts", response_model=list[S.AccountOut])
def list_accounts(company_id: int, db: Session = Depends(get_db)):
    _company(db, company_id)
    return db.execute(select(m.Account).where(m.Account.company_id == company_id)).scalars().all()


# ---------- upload / engine ----------
@router.post("/companies/{company_id}/upload", response_model=S.UploadOut)
async def upload(company_id: int, file: UploadFile = File(...), source_kind: str = Form("bank"),
                 account_label: str = Form(""), is_personal: bool = Form(False), db: Session = Depends(get_db)):
    company = _company(db, company_id)
    if source_kind not in ("bank", "card", "tally", "generic"):
        raise HTTPException(400, "source_kind must be bank, card, tally or generic")
    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "File is larger than 25 MB. Export a shorter date range (12–24 months is enough).")
    head = content[:8]
    fname = (file.filename or "").lower()
    if fname.endswith((".xlsx", ".xlsm")) and not head.startswith(b"PK"):
        raise HTTPException(400, "This is not a real Excel file. Download the statement again as .xlsx from net banking.")
    if fname.endswith(".pdf") and not head.startswith(b"%PDF"):
        raise HTTPException(400, "This is not a real PDF file.")
    if not fname.endswith((".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".tsv", ".pdf", ".xml")):
        raise HTTPException(400, "Upload an Excel (.xlsx/.xls), CSV, PDF or Tally XML file.")
    label = account_label.strip() or {"bank": "Bank account", "card": "Company card", "tally": "Tally export", "generic": "Other"}[source_kind]
    kind = "personal" if is_personal else ("tally" if source_kind == "tally" else ("card" if source_kind == "card" else "bank"))
    acc = db.execute(select(m.Account).where(m.Account.company_id == company_id, m.Account.label == label)).scalar_one_or_none()
    if not acc:
        acc = m.Account(company_id=company_id, label=label, kind=kind)
        db.add(acc)
        db.flush()
    batch = m.ImportBatch(company_id=company_id, account_id=acc.id, filename=file.filename or "upload", source_kind=source_kind)
    db.add(batch)
    db.flush()
    try:
        if (file.filename or "").lower().endswith(".xml"):
            rows, fmt, skipped = parse_tally_xml(content)
        else:
            rows, fmt, skipped = parse_rows(content, file.filename or "upload.xlsx", source_kind)
    except ValueError as e:
        batch.error = str(e)
        db.commit()
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("ittracker").exception("upload parse failed")
        batch.error = "Could not read this file. Export the statement as Excel from net banking and try again."
        db.commit()
        raise HTTPException(400, batch.error)
    added, dup = runner.ingest_rows(db, company, acc, batch, rows, source_kind, is_personal)
    batch.rows_imported, batch.rows_skipped, batch.detected_format = added, skipped + dup, fmt
    db.commit()
    summary = runner.run_engine(db, company_id)
    db.refresh(batch)
    out = S.ImportBatchOut.model_validate(batch)
    out.account_label = acc.label
    return S.UploadOut(batch=out, engine=S.EngineSummary(**summary))


@router.post("/companies/{company_id}/run", response_model=S.EngineSummary)
def run(company_id: int, db: Session = Depends(get_db)):
    _company(db, company_id)
    return S.EngineSummary(**runner.run_engine(db, company_id))


@router.get("/companies/{company_id}/imports", response_model=list[S.ImportBatchOut])
def imports(company_id: int, db: Session = Depends(get_db)):
    _company(db, company_id)
    batches = db.execute(select(m.ImportBatch).where(m.ImportBatch.company_id == company_id).order_by(m.ImportBatch.id.desc())).scalars().all()
    accs = {a.id: a.label for a in db.execute(select(m.Account).where(m.Account.company_id == company_id)).scalars()}
    out = []
    for b in batches:
        o = S.ImportBatchOut.model_validate(b)
        o.account_label = accs.get(b.account_id)
        out.append(o)
    return out


# ---------- dashboard ----------
@router.get("/companies/{company_id}/dashboard")
def dashboard(company_id: int, month: str | None = None, db: Session = Depends(get_db)):
    _company(db, company_id)
    today = today_ist()
    try:
        y, mo = (int(x) for x in (month or today.strftime("%Y-%m")).split("-"))
    except ValueError:
        raise HTTPException(400, "month must look like 2026-09")
    start = date(y, mo, 1)
    end = date(y, mo, monthrange(y, mo)[1])
    streams = db.execute(select(m.Stream).where(m.Stream.company_id == company_id, m.Stream.dismissed == False)).scalars().all()  # noqa: E712
    live = [s for s in streams if s.status in LIVE or (s.status == "needs_confirm" and s.confidence >= 45)]

    cash_out = 0.0
    meq = 0.0
    by_cat: dict[str, dict] = {}
    committed, manual = 0.0, 0.0
    for s in live:
        me = monthly_equivalent(s.expected_amount, s.cycle_months, s.stream_type)
        meq += me
        c = by_cat.setdefault(s.category, {"category": s.category, "monthly_equivalent": 0.0, "count": 0})
        c["monthly_equivalent"] += me
        c["count"] += 1
        if s.auto_renew:
            committed += me
        else:
            manual += me
        if s.stream_type == "prepaid" or not s.cycle_months:
            cash_out += me
        else:
            cash_out += (s.expected_amount or 0) * len(due_dates_in_range(s.next_due, s.cycle_months, start, end))
    # already-paid occurrences in this month for streams whose next_due already rolled past (avoid double count):
    live_ids = [s.id for s in live]
    paid_rows = db.execute(select(m.Occurrence.stream_id, func.sum(m.Occurrence.amount_paid)).where(
        m.Occurrence.company_id == company_id, m.Occurrence.date >= start, m.Occurrence.date <= end,
        m.Occurrence.unpaid == False, m.Occurrence.stream_id.in_(live_ids)).group_by(m.Occurrence.stream_id)).all() if live_ids else []  # noqa: E712
    paid_by_stream = {sid: float(v or 0) for sid, v in paid_rows}
    paid_this_month = sum(paid_by_stream.values())
    cash_breakdown = {"paid": 0.0, "still_due": 0.0, "estimate": 0.0}
    if start <= today <= end:
        # this month = what was already paid + what is still due (incl. overdue items, due "now") + run-rate for pay-as-you-go
        remaining = 0.0
        for s in live:
            if s.stream_type == "prepaid" or not s.cycle_months:
                continue
            if s.status in ("overdue", "charge_missed") and s.next_due and s.next_due < today and s.id not in paid_by_stream:
                remaining += s.expected_amount or 0
                continue
            remaining += (s.expected_amount or 0) * len(due_dates_in_range(s.next_due, s.cycle_months, max(start, today), end))
        estimate = sum(max(0.0, monthly_equivalent(s.expected_amount, s.cycle_months, s.stream_type) - paid_by_stream.get(s.id, 0.0))
                       for s in live if s.stream_type == "prepaid" or not s.cycle_months)
        cash_out = paid_this_month + remaining + estimate
        cash_breakdown = {"paid": round(paid_this_month, 2), "still_due": round(remaining, 2), "estimate": round(estimate, 2)}

    calendar = []
    for i in range(12):
        ms = (start + relativedelta(months=i))
        me_ = date(ms.year, ms.month, monthrange(ms.year, ms.month)[1])
        items, tot = [], 0.0
        for s in live:
            if s.stream_type == "prepaid" or not s.cycle_months:
                tot += monthly_equivalent(s.expected_amount, s.cycle_months, s.stream_type)
                continue
            for d in due_dates_in_range(s.next_due, s.cycle_months, ms, me_):
                items.append({"stream_id": s.id, "vendor_name": s.vendor_name, "product": s.product, "amount": s.expected_amount, "due": d.isoformat()})
                tot += s.expected_amount or 0
        if i == 0 and start <= today <= end:
            tot = cash_out   # current month: same number as the headline (paid so far + still due + estimate)
        calendar.append({"month": ms.strftime("%Y-%m"), "cash_out": round(tot, 2), "items": sorted(items, key=lambda x: x["due"])})

    next_dues = sorted([s for s in live if s.next_due], key=lambda s: s.next_due)[:5]
    accs = db.execute(select(m.Account).where(m.Account.company_id == company_id)).scalars().all()
    health = []
    for a in accs:
        last_date = db.execute(select(func.max(m.RawRow.date)).where(m.RawRow.account_id == a.id)).scalar()
        last_imp = db.execute(select(func.max(m.ImportBatch.created_at)).where(m.ImportBatch.account_id == a.id, m.ImportBatch.error == None)).scalar()  # noqa: E711
        health.append({"account_label": a.label, "source_kind": a.kind, "last_data_date": last_date.isoformat() if last_date else None,
                       "last_import_at": last_imp.isoformat() if last_imp else None,
                       "stale": bool(last_date and (today - last_date).days > 45)})
    return {
        "month": start.strftime("%Y-%m"), "cash_out_month": round(cash_out, 2), "cash_breakdown": cash_breakdown, "monthly_equivalent": round(meq, 2),
        "annualised": round(meq * 12, 2),
        "active_count": sum(1 for s in streams if s.status in LIVE),
        "due_soon_count": sum(1 for s in streams if s.status in LIVE and s.next_due and 0 <= (s.next_due - today).days <= 7),
        "overdue_count": sum(1 for s in streams if s.status in ("overdue", "charge_missed")),
        "needs_confirm_count": db.execute(select(func.count(m.Question.id)).where(m.Question.company_id == company_id, m.Question.answered == False)).scalar(),  # noqa: E712
        "by_category": sorted([{**v, "monthly_equivalent": round(v["monthly_equivalent"], 2)} for v in by_cat.values()], key=lambda x: -x["monthly_equivalent"]),
        "next_dues": [stream_out(s) for s in next_dues],
        "calendar": calendar,
        "committed_vs_manual": {"auto_renew": round(committed, 2), "manual": round(manual, 2)},
        "sync_health": health,
    }


# ---------- streams ----------
@router.get("/companies/{company_id}/streams", response_model=list[S.StreamOut])
def list_streams(company_id: int, status: str | None = None, category: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    _company(db, company_id)
    stmt = select(m.Stream).where(m.Stream.company_id == company_id)
    if status:
        stmt = stmt.where(m.Stream.status == status)
    else:
        stmt = stmt.where(m.Stream.dismissed == False)  # noqa: E712
    if category:
        stmt = stmt.where(m.Stream.category == category)
    rows = db.execute(stmt).scalars().all()
    if q:
        ql = q.lower()
        rows = [s for s in rows if ql in (s.vendor_name or "").lower() or ql in (s.product or "").lower() or ql in (s.payee_name or "").lower()]
    order = {"overdue": 0, "charge_missed": 0, "due_soon": 1, "needs_confirm": 2, "active": 3, "stopped": 4, "amc_lapsed": 4, "one_time": 5, "cancelled": 6, "dismissed": 7}
    rows.sort(key=lambda s: (order.get(s.status, 9), s.next_due or date.max, -(s.expected_amount or 0)))
    return [stream_out(s) for s in rows]


@router.get("/companies/{company_id}/streams/{sid}", response_model=S.StreamDetail)
def get_stream(company_id: int, sid: int, db: Session = Depends(get_db)):
    st = _stream(db, company_id, sid)
    occs = db.execute(select(m.Occurrence).where(m.Occurrence.stream_id == sid).order_by(m.Occurrence.date.desc())).scalars().all()
    base = stream_out(st).model_dump()
    return S.StreamDetail(**base, occurrences=[S.OccurrenceOut.model_validate(o) for o in occs], amount_history=st.amount_history or [])


@router.post("/companies/{company_id}/streams", response_model=S.StreamOut)
def create_stream(company_id: int, body: S.StreamCreate, db: Session = Depends(get_db)):
    _company(db, company_id)
    months = CYCLE_MONTHS.get(body.cycle)
    stream_type = "one_time" if body.cycle == "one_time" else "subscription"
    next_due = body.next_due
    if not next_due and body.last_paid_date and months:
        next_due = body.last_paid_date + relativedelta(months=months)
    st = m.Stream(company_id=company_id, stream_key="manual|pending", vendor_name=body.vendor_name.strip(), payee_name=body.vendor_name.strip(),
                  product=body.product, category=body.category, stream_type=stream_type, cycle=body.cycle if months else "irregular",
                  cycle_months=months, expected_amount=body.expected_amount, avg_amount=body.expected_amount, last_amount=body.expected_amount,
                  first_seen=body.last_paid_date, last_paid_date=body.last_paid_date, next_due=next_due, confidence=100,
                  auto_renew=body.auto_renew, paid_from=body.paid_from, owner_name=body.owner_name, pay_url=body.pay_url, notes=body.notes,
                  is_user_modified=True, user_fields={"manual": True}, sources=["manual"], occurrences_count=1 if body.last_paid_date else 0,
                  flags=["added_manually"])
    db.add(st)
    db.flush()
    st.stream_key = f"manual|{st.id}"
    _recompute_status(st)
    db.commit()
    db.refresh(st)
    return stream_out(st)


@router.patch("/companies/{company_id}/streams/{sid}", response_model=S.StreamOut)
def patch_stream(company_id: int, sid: int, body: S.StreamPatch, db: Session = Depends(get_db)):
    st = _stream(db, company_id, sid)
    data = body.model_dump(exclude_unset=True)
    uf = dict(st.user_fields or {})
    for k, v in data.items():
        if k == "cycle":
            if v == "one_time":
                st.stream_type, st.cycle, st.cycle_months, st.next_due = "one_time", "irregular", None, None
                uf.update(stream_type="one_time", cycle="irregular", cycle_months=None)
                continue
            st.cycle = v
            st.cycle_months = CYCLE_MONTHS.get(v)
            uf["cycle_months"] = st.cycle_months
            if st.stream_type == "one_time":
                st.stream_type = "subscription"
                uf["stream_type"] = "subscription"
            if "next_due" not in data and st.last_paid_date and st.cycle_months:
                st.next_due = st.last_paid_date + relativedelta(months=int(st.cycle_months))
                uf["next_due"] = st.next_due.isoformat()
        if k == "status":
            if v not in ("active", "cancelled", "stopped", "one_time"):
                raise HTTPException(400, "status can be set to active, cancelled, stopped or one_time")
        setattr(st, k, v)
        uf[k] = v.isoformat() if isinstance(v, date) else v
    if "next_due" in data:
        uf["next_due_basis"] = st.last_paid_date.isoformat() if st.last_paid_date else ""
    st.user_fields = uf
    st.is_user_modified = True
    if any(k in data for k in ("cycle", "expected_amount", "vendor_name", "product", "status", "next_due")):
        st.confidence = 100
    _recompute_status(st)
    if data.get("status") in ("active", "stopped", "one_time"):
        st.status = data["status"]
    db.commit()
    db.refresh(st)
    return stream_out(st)


@router.post("/companies/{company_id}/streams/{sid}/mark-paid", response_model=S.StreamOut)
def mark_paid(company_id: int, sid: int, body: S.MarkPaid, db: Session = Depends(get_db)):
    st = _stream(db, company_id, sid)
    amount = body.amount or st.expected_amount or 0.0
    desc = f"{st.payee_name or st.vendor_name} | marked paid in IT Tracker"
    company = db.get(m.Company, company_id)
    batch = m.ImportBatch(company_id=company_id, filename="manual", source_kind="manual", rows_imported=1)
    db.add(batch)
    db.flush()
    runner.ingest_rows(db, company, None, batch, [{"date": body.date, "amount": amount, "direction": "debit", "raw_description": desc}], "manual")
    # for manual streams the engine won't rebuild them; roll the due date here
    st.last_paid_date = body.date
    st.last_amount = amount
    if st.cycle_months:
        st.next_due = body.date + relativedelta(months=int(st.cycle_months))
    uf = dict(st.user_fields or {})
    # marking paid confirms the line as it stands: keep its cycle and amount even if the manual date breaks the rhythm
    uf.update(cycle=st.cycle, cycle_months=st.cycle_months, stream_type=st.stream_type, expected_amount=st.expected_amount)
    if st.paid_from:
        uf["paid_from"] = st.paid_from
    uf.pop("next_due", None); uf.pop("next_due_basis", None)
    st.user_fields, st.is_user_modified, st.confidence = uf, True, 100
    st.occurrences_count = (st.occurrences_count or 0) + 1
    if "manual" not in (st.sources or []):
        st.sources = list(st.sources or []) + ["manual"]
    _recompute_status(st)
    db.commit()
    if not st.stream_key.startswith("manual|"):
        # make sure the learned payee maps to this vendor so the manual row joins the same stream on re-run
        if st.vendor_id and st.payee_name:
            db.add(m.VendorAlias(vendor_id=st.vendor_id, pattern=runner.clean_payee(desc), kind="exact", product=st.product, company_id=company_id))
            db.commit()
        runner.run_engine(db, company_id)
        st = db.get(m.Stream, sid) or st
    db.refresh(st)
    return stream_out(st)


@router.post("/companies/{company_id}/streams/{sid}/confirm", response_model=S.StreamOut)
def confirm_stream(company_id: int, sid: int, body: S.ConfirmIn, db: Session = Depends(get_db)):
    st = _stream(db, company_id, sid)
    uf = dict(st.user_fields or {})
    if body.accept:
        st.confidence = 100
        st.is_user_modified = True
        uf["confirmed"] = True
    else:
        st.dismissed = True
        st.is_user_modified = True
        uf["dismissed"] = True
        if st.payee_name:
            not_it = db.execute(select(m.Vendor).where(m.Vendor.key == "not_it")).scalar_one()
            db.add(m.VendorAlias(vendor_id=not_it.id, pattern=st.payee_name, kind="exact", company_id=company_id))
    st.user_fields = uf
    _recompute_status(st)
    for q in db.execute(select(m.Question).where(m.Question.stream_id == sid, m.Question.answered == False)).scalars():  # noqa: E712
        q.answered, q.answer = True, "confirmed" if body.accept else "dismissed"
    db.commit()
    db.refresh(st)
    return stream_out(st)


# ---------- questions ----------
@router.get("/companies/{company_id}/questions", response_model=list[S.QuestionOut])
def questions(company_id: int, open: bool = True, db: Session = Depends(get_db)):
    _company(db, company_id)
    stmt = select(m.Question).where(m.Question.company_id == company_id)
    if open:
        stmt = stmt.where(m.Question.answered == False)  # noqa: E712
    return db.execute(stmt.order_by(m.Question.id)).scalars().all()


@router.post("/companies/{company_id}/questions/{qid}/answer", response_model=S.AnswerOut)
def answer(company_id: int, qid: int, body: S.AnswerIn, db: Session = Depends(get_db)):
    q = db.get(m.Question, qid)
    if not q or q.company_id != company_id:
        raise HTTPException(404, "Question not found")
    if q.answered:
        raise HTTPException(400, "Already answered")
    st = runner.answer_question(db, q, body.choice, body.text)
    q = db.get(m.Question, qid)
    return S.AnswerOut(question=S.QuestionOut.model_validate(q), stream=stream_out(st) if st else None)


# ---------- upcoming ----------
@router.get("/companies/{company_id}/upcoming")
def upcoming(company_id: int, days: int = 90, db: Session = Depends(get_db)):
    _company(db, company_id)
    today = today_ist()
    end = today + timedelta(days=days)
    streams = db.execute(select(m.Stream).where(m.Stream.company_id == company_id, m.Stream.dismissed == False)).scalars().all()  # noqa: E712
    months: dict[str, dict] = {}
    for s in streams:
        if s.status not in LIVE and not (s.status == "needs_confirm" and s.confidence >= 45):
            continue
        for d in due_dates_in_range(s.next_due, s.cycle_months, today - timedelta(days=45), end):
            if d < today and s.status not in ("overdue", "charge_missed"):
                continue
            key = d.strftime("%Y-%m")
            mth = months.setdefault(key, {"month": key, "total": 0.0, "items": []})
            item = stream_out(s).model_dump()
            item["due"] = d.isoformat()
            mth["items"].append(item)
            mth["total"] += s.expected_amount or 0
    out = sorted(months.values(), key=lambda x: x["month"])
    for mth in out:
        mth["items"].sort(key=lambda i: i["due"])
        mth["total"] = round(mth["total"], 2)
    return out


# ---------- vendors ----------
@router.get("/vendors", response_model=list[S.VendorOut])
def vendors(q: str | None = None, db: Session = Depends(get_db)):
    rows = db.execute(select(m.Vendor).where(m.Vendor.exclude == False).order_by(m.Vendor.name)).scalars().all()  # noqa: E712
    if q:
        rows = [v for v in rows if q.lower() in v.name.lower()]
    return rows


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(func.count(m.Vendor.id)))
    return {"ok": True, "time": datetime.utcnow().isoformat()}
