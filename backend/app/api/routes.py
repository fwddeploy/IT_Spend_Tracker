from __future__ import annotations
import inspect
import logging
import os
import re
from calendar import monthrange
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.responses import Response as RawResponse
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from app.db import get_db
from app import models as m
from app import auth
from app import reminders as R
from app.auth import Principal, current_user, require_company
from app.api import schemas as S
from app.engine import runner
from app.engine.runner import today_ist
from app.engine.status import compute_status, due_dates_in_range, monthly_equivalent
from app.engine.recurrence import CYCLE_MONTHS
from app.parsers.tabular import parse_rows, load_table
from app.parsers.tally_xml import parse_tally_xml

log = logging.getLogger("ittracker.api")
def inr(x: float) -> str:
    """Indian grouping: 2,45,568."""
    n = int(round(x or 0))
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n < 1000:
        return f"{sign}₹{n}"
    head, tail = str(n)[:-3], str(n)[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:]); head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"{sign}₹{','.join(groups)},{tail}"


router = APIRouter(prefix="/api")

VIEWER, ACCOUNTANT, OWNER = require_company("viewer"), require_company("accountant"), require_company("owner")
LIVE = ("active", "due_soon", "overdue", "charge_missed")


# ---------- helpers ----------
def _stream(db: Session, company_id: int, sid: int) -> m.Stream:
    st = db.get(m.Stream, sid)
    if not st or st.company_id != company_id:
        raise HTTPException(404, "Line item not found")
    return st


def _event(db: Session, company_id: int, p: Principal, action: str, target: str | None = None, detail: dict | None = None):
    db.add(m.Event(company_id=company_id, user=p.label, action=action, target=target, detail=detail))


# vendor id -> (key, entity_type); vendors rarely change, so a tiny in-process cache
_VCACHE: dict[int, tuple[str, str]] = {}


def _vendor_info(db: Session, vendor_id: int | None) -> tuple[str, str] | None:
    if not vendor_id:
        return None
    if vendor_id not in _VCACHE:
        v = db.get(m.Vendor, vendor_id)
        if not v:
            return None
        _VCACHE[vendor_id] = (v.key, v.entity_type)
    return _VCACHE[vendor_id]


# known per-seat list prices (INR / month). Tiny on purpose; return null when unsure.
PER_SEAT = {"microsoft365": [145.0, 660.0, 1140.0], "google_workspace": [136.9, 236.0, 736.0]}


def _seats(vendor_key: str | None, amount: float | None) -> tuple[int | None, float | None]:
    if not vendor_key or not amount or vendor_key not in PER_SEAT:
        return None, None
    for price in PER_SEAT[vendor_key]:
        k = round(amount / price)
        if 1 <= k <= 500 and abs(amount - k * price) <= 0.01 * amount:
            return int(k), price
    return None, None


FLAG_TEXT = {
    "one_time_licence": "One-time licence purchase",
    "cycle_from_invoice": "Cycle read from the invoice / narration",
    "cycle_from_vendor_default": "Cycle assumed from the vendor's usual billing",
    "price_changed": "Price changed since the earlier payments",
    "intro_price_renewal_may_be_higher": "Introductory price — renewal may be higher",
    "tds_deducted": "TDS was deducted before paying",
    "rcm_gst_payable": "Foreign vendor without GST — 18% GST payable under reverse charge",
    "paid_from_personal": "Paid from a personal card / account",
    "booked_not_paid": "Booked in Tally, no bank payment seen yet",
    "no_bank_match": "Bill in Tally but no matching bank payment",
    "forex_markup": "Bank forex markup fee included",
    "paid_taxable_only_check_gst": "Only the taxable value was paid — check GST",
    "paid_in_2_parts": "Paid in two parts",
    "added_manually": "Added by hand",
    "user_says_active": "You said this is still in use",
    "paid_elsewhere": "Paid from another account",
    "split_from_bundle": "Split out of a reseller bill",
    "supplier_changed": "Supplier changed (same product, new payee)",
}


def flag_human(f: str) -> str:
    if f in FLAG_TEXT:
        return FLAG_TEXT[f]
    mt = re.fullmatch(r"(\d+)_charges_per_cycle", f)
    if mt:
        return f"{mt.group(1)} charges every cycle (seats / add-ons)"
    mt = re.fullmatch(r"custom_(\d+)m", f)
    if mt:
        return f"Repeats every {mt.group(1)} months"
    mt = re.fullmatch(r"catch_up_(\d+)_cycles", f)
    if mt:
        return f"One payment covered {mt.group(1)} cycles (catch-up)"
    mt = re.fullmatch(r"topup_every_(\d+)d", f)
    if mt:
        return f"Topped up about every {mt.group(1)} days"
    mt = re.fullmatch(r"tds_(\d*)pct", f)
    if mt:
        return f"TDS {mt.group(1)}% deducted" if mt.group(1) else "TDS deducted"
    return f.replace("_", " ").capitalize()


def fy_label(d: date | None, fy_start_month: int) -> str | None:
    if not d:
        return None
    y = d.year if d.month >= fy_start_month else d.year - 1
    if fy_start_month == 1:
        return str(y)
    return f"{y}-{str(y + 1)[-2:]}"


def stream_out(st: m.Stream, db: Session | None = None, fy_start_month: int = 4) -> S.StreamOut:
    vinfo = _vendor_info(db, st.vendor_id) if db else None
    vkey = vinfo[0] if vinfo else None
    flags = st.flags or []
    extra = st.extra or {}
    rcm = round((st.expected_amount or 0) * 0.18, 2) if ("rcm_gst_payable" in flags or (vinfo and vinfo[1] == "foreign_no_gst")) and st.expected_amount else None
    qty, unit = _seats(vkey, st.expected_amount)
    if extra.get("quantity"):   # engine's own inference wins when it has one
        qty, unit = extra.get("quantity"), extra.get("unit_price")
    if extra.get("rcm_gst") is not None:
        rcm = extra["rcm_gst"]
    fy, history = None, list(extra.get("supplier_history") or [])
    if db:
        occs = db.execute(select(m.Occurrence.payee_clean, m.Occurrence.period_from, m.Occurrence.period_to, m.Occurrence.date)
                          .where(m.Occurrence.stream_id == st.id).order_by(m.Occurrence.date)).all()
        if occs:
            last = occs[-1]
            fy = fy_label(last[1] or last[2] or last[3], fy_start_month)
            if not history:
                for payee, *_ in occs:
                    if payee and payee not in history:
                        history.append(payee)
            if len(history) <= 1:
                history = []
    elif st.last_paid_date:
        fy = fy_label(st.last_paid_date, fy_start_month)
    return S.StreamOut(
        id=st.id, vendor_name=st.vendor_name, payee_name=st.payee_name, product=st.product, category=st.category,
        stream_type=st.stream_type, cycle=st.cycle, cycle_months=st.cycle_months, expected_amount=st.expected_amount,
        avg_amount=st.avg_amount, monthly_equivalent=round(monthly_equivalent(st.expected_amount, st.cycle_months, st.stream_type), 2),
        currency=st.currency, last_paid_date=st.last_paid_date, next_due=st.next_due, anchor_day=st.anchor_day, status=st.status,
        confidence=st.confidence, auto_renew=st.auto_renew, paid_from=st.paid_from, owner_name=st.owner_name, pay_url=st.pay_url,
        reminder_on=st.reminder_on, notes=st.notes, is_user_modified=st.is_user_modified, occurrences_count=st.occurrences_count,
        sources=st.sources or [], first_seen=st.first_seen, flags=flags,
        rcm_gst=rcm, quantity=qty, unit_price=unit, fy=fy, flags_human=[flag_human(f) for f in flags], supplier_history=history, change_note=extra.get("change_note"),
    )


def _recompute_status(st: m.Stream):
    st.status = compute_status(stream_type=st.stream_type, cycle=st.cycle, cycle_months=st.cycle_months, next_due=st.next_due,
                               last_paid_date=st.last_paid_date, auto_renew=st.auto_renew, confidence=st.confidence,
                               is_user_modified=st.is_user_modified, dismissed=st.dismissed,
                               cancelled=(st.user_fields or {}).get("status") == "cancelled")


def _me(db: Session, p: Principal) -> S.MeOut:
    return S.MeOut(user=S.UserOut.model_validate(p.user) if p.user else None,
                   companies=[S.CompanyRole(id=c.id, name=c.name, role=r) for c, r in auth.companies_for(db, p)])


# ---------- auth ----------
@router.post("/auth/register", response_model=S.MeOut)
def register(body: S.RegisterIn, response: Response, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Enter a valid email")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if db.execute(select(m.User.id).where(m.User.email == email)).first():
        raise HTTPException(400, "An account with this email already exists — log in instead")
    u = m.User(name=body.name.strip() or email, email=email, password_hash=auth.hash_password(body.password))
    db.add(u)
    db.flush()
    c = m.Company(name=body.company_name.strip() or f"{u.name}'s company")
    db.add(c)
    db.flush()
    db.add(m.Membership(user_id=u.id, company_id=c.id, role="owner"))
    db.commit()
    auth.set_session(response, u.id)
    return _me(db, Principal(user=u))


@router.post("/auth/login", response_model=S.MeOut)
def login(body: S.LoginIn, response: Response, db: Session = Depends(get_db)):
    u = db.execute(select(m.User).where(m.User.email == body.email.strip().lower())).scalar_one_or_none()
    if not u or not auth.verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Wrong email or password")
    auth.set_session(response, u.id)
    return _me(db, Principal(user=u))


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    auth.clear_session(response)
    return None


@router.get("/auth/me", response_model=S.MeOut)
def me(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    return _me(db, p)


@router.post("/auth/invite", response_model=S.InviteOut)
def invite(body: S.InviteIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    if body.role not in auth.ROLES:
        raise HTTPException(400, "role must be owner, accountant or viewer")
    if auth.role_for(db, p, body.company_id) != "owner":
        raise HTTPException(403, "Only an owner can invite people")
    email = body.email.strip().lower()
    u = db.execute(select(m.User).where(m.User.email == email)).scalar_one_or_none()
    temp = None
    if not u:
        temp = auth.temp_password()
        u = m.User(name=(body.name or email.split("@")[0]).strip(), email=email, password_hash=auth.hash_password(temp))
        db.add(u)
        db.flush()
    mem = auth.membership(db, u.id, body.company_id)
    if mem:
        mem.role = body.role
    else:
        db.add(m.Membership(user_id=u.id, company_id=body.company_id, role=body.role))
    _event(db, body.company_id, p, "invite", email, {"role": body.role})
    db.commit()
    return S.InviteOut(email=email, temp_password=temp, role=body.role)


# ---------- companies ----------
@router.get("/companies", response_model=list[S.CompanyOut])
def list_companies(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for c, role in auth.companies_for(db, p):
        o = S.CompanyOut.model_validate(c)
        o.role = role
        out.append(o)
    return out


@router.post("/companies", response_model=S.CompanyOut)
def create_company(body: S.CompanyIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    c = m.Company(name=body.name.strip(), gstin=body.gstin, fy_start_month=body.fy_start_month)
    db.add(c)
    db.flush()
    if p.user:
        db.add(m.Membership(user_id=p.user.id, company_id=c.id, role="owner"))
    db.commit()
    db.refresh(c)
    o = S.CompanyOut.model_validate(c)
    o.role = "owner"
    return o


@router.get("/companies/{company_id}", response_model=S.CompanyOut)
def get_company(company: m.Company = Depends(VIEWER), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    o = S.CompanyOut.model_validate(company)
    o.role = auth.role_for(db, p, company.id)
    return o


def _settings(c: m.Company) -> S.SettingsOut:
    return S.SettingsOut(name=c.name, gstin=c.gstin, fy_start_month=c.fy_start_month, short_name=c.short_name, owner_phone=c.owner_phone,
                         owner_email=c.owner_email, accountant_email=c.accountant_email, whatsapp_enabled=bool(c.whatsapp_enabled),
                         email_enabled=bool(c.email_enabled), reminder_days_before={**m.DEFAULT_REMINDER_DAYS, **(c.reminder_days_before or {})},
                         weekly_digest_day=c.weekly_digest_day)


@router.get("/companies/{company_id}/settings", response_model=S.SettingsOut)
def get_settings(company: m.Company = Depends(VIEWER)):
    return _settings(company)


@router.patch("/companies/{company_id}/settings", response_model=S.SettingsOut)
def patch_settings(body: S.SettingsPatch, company: m.Company = Depends(OWNER), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if "fy_start_month" in data and not (1 <= (data["fy_start_month"] or 0) <= 12):
        raise HTTPException(400, "fy_start_month must be 1-12")
    if data.get("weekly_digest_day") not in (None, "mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        raise HTTPException(400, "weekly_digest_day must be mon..sun or null")
    if "reminder_days_before" in data and data["reminder_days_before"] is not None:
        bad = set(data["reminder_days_before"]) - {"monthly", "quarterly", "yearly"}
        if bad:
            raise HTTPException(400, "reminder_days_before keys must be monthly, quarterly, yearly")
        data["reminder_days_before"] = {**m.DEFAULT_REMINDER_DAYS, **(company.reminder_days_before or {}), **data["reminder_days_before"]}
    if "name" in data and not (data["name"] or "").strip():
        raise HTTPException(400, "name cannot be empty")
    for k, v in data.items():
        setattr(company, k, v.strip() if isinstance(v, str) else v)
    _event(db, company.id, p, "settings", None, {k: v for k, v in data.items()})
    db.commit()
    db.refresh(company)
    return _settings(company)


@router.delete("/companies/{company_id}", status_code=204)
def delete_company(company: m.Company = Depends(OWNER), db: Session = Depends(get_db)):
    cid = company.id
    # children first (no ORM cascades on purpose — keeps the models plain)
    db.execute(delete(m.ReminderLog).where(m.ReminderLog.company_id == cid))
    db.execute(delete(m.Event).where(m.Event.company_id == cid))
    db.execute(delete(m.Question).where(m.Question.company_id == cid))
    db.execute(delete(m.Occurrence).where(m.Occurrence.company_id == cid))
    db.execute(delete(m.Stream).where(m.Stream.company_id == cid))
    db.execute(delete(m.RawRow).where(m.RawRow.company_id == cid))
    db.execute(delete(m.ImportBatch).where(m.ImportBatch.company_id == cid))
    db.execute(delete(m.Account).where(m.Account.company_id == cid))
    db.execute(delete(m.VendorAlias).where(m.VendorAlias.company_id == cid))
    db.execute(delete(m.Membership).where(m.Membership.company_id == cid))
    db.delete(company)
    db.commit()
    log.info("company deleted company_id=%s", cid)
    return RawResponse(status_code=204)


@router.get("/companies/{company_id}/accounts", response_model=list[S.AccountOut])
def list_accounts(company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    return db.execute(select(m.Account).where(m.Account.company_id == company.id)).scalars().all()


# ---------- aliases (hidden payees / learned answers) ----------
@router.get("/companies/{company_id}/aliases", response_model=list[S.AliasOut])
def list_aliases(company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    rows = db.execute(select(m.VendorAlias, m.Vendor).join(m.Vendor, m.Vendor.id == m.VendorAlias.vendor_id)
                      .where(m.VendorAlias.company_id == company.id).order_by(m.VendorAlias.id.desc())).all()
    out = []
    for a, v in rows:
        pat = a.pattern
        if a.kind == "regex" and pat.startswith("^") and pat.endswith("$"):
            pat = re.sub(r"\\(.)", r"\1", pat[1:-1])
        out.append(S.AliasOut(id=a.id, pattern=pat, vendor_name=v.name, product=a.product, created_at=None, hidden=(v.key == "not_it")))
    return out


@router.delete("/companies/{company_id}/aliases/{alias_id}", status_code=204)
def delete_alias(alias_id: int, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(m.VendorAlias, alias_id)
    if not a or a.company_id != company.id:
        raise HTTPException(404, "Alias not found")
    _event(db, company.id, p, "alias_delete", a.pattern, {"vendor_id": a.vendor_id, "product": a.product})
    payee = re.sub(r"^\^|\$$", "", a.pattern).replace("\\", "")
    for st in db.execute(select(m.Stream).where(m.Stream.company_id == company.id, m.Stream.payee_name == payee)).scalars():
        if st.dismissed:
            uf = dict(st.user_fields or {})
            uf.pop("dismissed", None); uf.pop("confirmed", None)
            st.dismissed, st.user_fields, st.is_user_modified = False, uf, bool(uf)
    db.delete(a)
    db.commit()
    runner.run_engine(db, company.id)
    return RawResponse(status_code=204)


# ---------- upload / engine ----------
BANKS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "YES", "INDUSIND", "BOB", "PNB", "CANARA"]
_BANK_RX = {b: re.compile(rf"\b{b}\b") for b in BANKS}
_BANK_RX["SBI"] = re.compile(r"\bSBI\b|STATE BANK OF INDIA")
_BANK_RX["BOB"] = re.compile(r"\bBOB\b|BANK OF BARODA")
_BANK_RX["PNB"] = re.compile(r"\bPNB\b|PUNJAB NATIONAL BANK")
_BANK_RX["YES"] = re.compile(r"\bYES BANK\b")


def detect_bank(content: bytes, filename: str) -> str | None:
    """Look at the first 40 rows of the file (statement header) for a bank name."""
    text = ""
    try:
        if not filename.lower().endswith((".pdf", ".xml")):
            df = load_table(content, filename)
            text = " ".join(str(v) for v in df.head(40).to_numpy().ravel() if v is not None).upper()
    except Exception:  # noqa: BLE001
        text = ""
    text += " " + filename.upper().replace("_", " ").replace("-", " ")
    for b in BANKS:
        if _BANK_RX[b].search(text):
            return b
    return None


def _parse(content: bytes, filename: str, source_kind: str, pdf_password: str | None):
    if filename.lower().endswith(".xml"):
        return parse_tally_xml(content)
    if pdf_password and "pdf_password" in inspect.signature(parse_rows).parameters:
        return parse_rows(content, filename, source_kind, pdf_password=pdf_password)
    return parse_rows(content, filename, source_kind)


@router.post("/companies/{company_id}/upload", response_model=S.UploadOut)
async def upload(file: UploadFile = File(...), source_kind: str = Form("bank"), account_label: str = Form(""),
                 is_personal: bool = Form(False), pdf_password: str | None = Form(None),
                 company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    company_id = company.id
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
    log.info("upload company_id=%s file=%s kind=%s bytes=%s", company_id, file.filename, source_kind, len(content))
    label = account_label.strip() or {"bank": "Bank account", "card": "Company card", "tally": "Tally export", "generic": "Other"}[source_kind]
    kind = "personal" if is_personal else ("tally" if source_kind == "tally" else ("card" if source_kind == "card" else "bank"))
    bank = detect_bank(content, file.filename or "") if source_kind in ("bank", "card", "generic") else None
    acc = db.execute(select(m.Account).where(m.Account.company_id == company_id, m.Account.label == label)).scalar_one_or_none()
    if not acc:
        acc = m.Account(company_id=company_id, label=label, kind=kind, bank_name=bank)
        db.add(acc)
        db.flush()
    elif bank and not acc.bank_name:
        acc.bank_name = bank
    batch = m.ImportBatch(company_id=company_id, account_id=acc.id, filename=file.filename or "upload", source_kind=source_kind)
    db.add(batch)
    db.flush()
    try:
        rows, fmt, skipped = _parse(content, file.filename or "upload.xlsx", source_kind, pdf_password)
    except ValueError as e:
        batch.error = str(e)
        db.commit()
        raise HTTPException(400, str(e))
    except Exception:  # noqa: BLE001
        log.exception("upload parse failed company_id=%s", company_id)
        batch.error = "Could not read this file. Export the statement as Excel from net banking and try again."
        db.commit()
        raise HTTPException(400, batch.error)
    added, dup = runner.ingest_rows(db, company, acc, batch, rows, source_kind, is_personal)
    batch.rows_imported, batch.rows_skipped, batch.detected_format = added, skipped + dup, fmt
    _event(db, company_id, p, "upload", file.filename, {"rows_imported": added, "rows_skipped": skipped + dup, "format": fmt, "account": acc.label})
    db.commit()
    summary = runner.run_engine(db, company_id)
    db.refresh(batch)
    out = S.ImportBatchOut.model_validate(batch)
    out.account_label = acc.label
    hint = None
    if added == 0:
        hint = "This statement was already uploaded" if dup > 0 else "No payment rows were found in this file"
    return S.UploadOut(batch=out, engine=S.EngineSummary(**summary), detected_bank=bank, hint=hint)


@router.post("/companies/{company_id}/run", response_model=S.EngineSummary)
def run(company: m.Company = Depends(ACCOUNTANT), db: Session = Depends(get_db)):
    return S.EngineSummary(**runner.run_engine(db, company.id))


@router.get("/companies/{company_id}/imports", response_model=list[S.ImportBatchOut])
def imports(company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    company_id = company.id
    batches = db.execute(select(m.ImportBatch).where(m.ImportBatch.company_id == company_id).order_by(m.ImportBatch.id.desc())).scalars().all()
    accs = {a.id: a.label for a in db.execute(select(m.Account).where(m.Account.company_id == company_id)).scalars()}
    out = []
    for b in batches:
        o = S.ImportBatchOut.model_validate(b)
        o.account_label = accs.get(b.account_id)
        out.append(o)
    return out


# ---------- dashboard ----------
def _month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def _dashboard(db: Session, company: m.Company, start: date, n_months: int, today: date) -> dict:
    """Numbers for `n_months` starting at `start` (1st of a month). Past months = actual payments, the current
    month = paid so far + still due + run-rate estimate, future months = dues."""
    company_id = company.id
    end = _month_end(start + relativedelta(months=n_months - 1))
    streams = db.execute(select(m.Stream).where(m.Stream.company_id == company_id, m.Stream.dismissed == False)).scalars().all()  # noqa: E712
    live = [s for s in streams if s.status in LIVE or (s.status == "needs_confirm" and s.confidence >= 45)]
    live_ids = [s.id for s in live]
    sname = {s.id: s for s in streams}

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

    # actual payments in the window (for past months and the "paid so far" part of the current month)
    occs = db.execute(select(m.Occurrence).where(m.Occurrence.company_id == company_id, m.Occurrence.date >= start, m.Occurrence.date <= end,
                                                 m.Occurrence.unpaid == False, m.Occurrence.stream_id.in_(list(sname)))).scalars().all() if sname else []  # noqa: E712
    cur_start = date(today.year, today.month, 1)
    cash_breakdown = {"paid": 0.0, "still_due": 0.0, "estimate": 0.0}

    def month_numbers(ms: date) -> tuple[float, list[dict]]:
        me_ = _month_end(ms)
        items: list[dict] = []
        if me_ < cur_start:   # past month: what actually went out
            tot = 0.0
            for o in occs:
                if ms <= o.date <= me_:
                    s = sname[o.stream_id]
                    items.append({"stream_id": s.id, "vendor_name": s.vendor_name, "product": s.product, "amount": o.amount_paid, "due": o.date.isoformat(), "paid": True})
                    tot += o.amount_paid
            return tot, items
        tot = 0.0
        for s in live:
            if s.stream_type == "prepaid" or not s.cycle_months:
                tot += monthly_equivalent(s.expected_amount, s.cycle_months, s.stream_type)
                continue
            for d in due_dates_in_range(s.next_due, s.cycle_months, ms, me_):
                items.append({"stream_id": s.id, "vendor_name": s.vendor_name, "product": s.product, "amount": s.expected_amount, "due": d.isoformat()})
                tot += s.expected_amount or 0
        if ms <= today <= me_:
            # this month = paid so far + still due (incl. overdue, due "now") + run-rate for pay-as-you-go
            paid_by_stream: dict[int, float] = {}
            for o in occs:
                if ms <= o.date <= me_ and o.stream_id in live_ids:
                    paid_by_stream[o.stream_id] = paid_by_stream.get(o.stream_id, 0.0) + o.amount_paid
            paid = sum(paid_by_stream.values())
            remaining = 0.0
            for s in live:
                if s.stream_type == "prepaid" or not s.cycle_months:
                    continue
                if s.status in ("overdue", "charge_missed") and s.next_due and s.next_due < today and s.id not in paid_by_stream:
                    remaining += s.expected_amount or 0
                    continue
                remaining += (s.expected_amount or 0) * len(due_dates_in_range(s.next_due, s.cycle_months, max(ms, today), me_))
            estimate = sum(max(0.0, monthly_equivalent(s.expected_amount, s.cycle_months, s.stream_type) - paid_by_stream.get(s.id, 0.0))
                           for s in live if s.stream_type == "prepaid" or not s.cycle_months)
            tot = paid + remaining + estimate
            cash_breakdown.update(paid=round(paid, 2), still_due=round(remaining, 2), estimate=round(estimate, 2))
        return tot, items

    calendar = []
    for i in range(n_months):
        ms = start + relativedelta(months=i)
        tot, items = month_numbers(ms)
        calendar.append({"month": ms.strftime("%Y-%m"), "cash_out": round(tot, 2), "items": sorted(items, key=lambda x: x["due"])})
    cash_out = calendar[0]["cash_out"]

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
        "month": start.strftime("%Y-%m"), "cash_out_month": cash_out, "cash_breakdown": cash_breakdown, "monthly_equivalent": round(meq, 2),
        "annualised": round(meq * 12, 2),
        "active_count": sum(1 for s in streams if s.status in LIVE),
        "due_soon_count": sum(1 for s in streams if s.status in LIVE and s.next_due and 0 <= (s.next_due - today).days <= 7),
        "overdue_count": sum(1 for s in streams if s.status in ("overdue", "charge_missed")),
        "needs_confirm_count": db.execute(select(func.count(m.Question.id)).where(m.Question.company_id == company_id, m.Question.answered == False)).scalar(),  # noqa: E712
        "by_category": sorted([{**v, "monthly_equivalent": round(v["monthly_equivalent"], 2)} for v in by_cat.values()], key=lambda x: -x["monthly_equivalent"]),
        "next_dues": [stream_out(s, db, company.fy_start_month) for s in next_dues],
        "calendar": calendar,
        "committed_vs_manual": {"auto_renew": round(committed, 2), "manual": round(manual, 2)},
        "sync_health": health,
    }


@router.get("/companies/{company_id}/dashboard")
def dashboard(month: str | None = None, fy: int | None = None, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    today = today_ist()
    if fy:
        start = date(fy, company.fy_start_month or 4, 1)
        out = _dashboard(db, company, start, 12, today)
        label = f"FY {fy}" if company.fy_start_month == 1 else f"FY {fy}-{str(fy + 1)[-2:]}"
        out.update(period=label, fy=fy, cash_out_period=round(sum(c["cash_out"] for c in out["calendar"]), 2))
        return out
    try:
        y, mo = (int(x) for x in (month or today.strftime("%Y-%m")).split("-"))
        start = date(y, mo, 1)
    except ValueError:
        raise HTTPException(400, "month must look like 2026-09")
    out = _dashboard(db, company, start, 12, today)
    out["period"] = start.strftime("%b %Y")
    return out


@router.get("/companies/{company_id}/share-text")
def share_text(company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    today = today_ist()
    d = _dashboard(db, company, date(today.year, today.month, 1), 1, today)
    lines = [f"IT Tracker · {company.short_name or company.name}",
             f"Going out in {today.strftime('%b %Y')}: {inr(d['cash_out_month'])}",
             f"Monthly-equivalent: {inr(d['monthly_equivalent'])} ({inr(d['annualised'])} a year)"]
    if d["next_dues"]:
        lines.append("Next dues:")
        for s in d["next_dues"]:
            lines.append(f"• {s.next_due.strftime('%d %b')} – {s.vendor_name}{' ' + s.product if s.product else ''} {inr(s.expected_amount or 0)}")
    if d["overdue_count"]:
        lines.append(f"Overdue: {d['overdue_count']}")
    if d["needs_confirm_count"]:
        lines.append(f"{d['needs_confirm_count']} lines need a look")
    return {"text": "\n".join(lines)}


# ---------- streams ----------
@router.get("/companies/{company_id}/streams", response_model=list[S.StreamOut])
def list_streams(status: str | None = None, category: str | None = None, q: str | None = None, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    stmt = select(m.Stream).where(m.Stream.company_id == company.id)
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
    return [stream_out(s, db, company.fy_start_month) for s in rows]


@router.get("/companies/{company_id}/streams/{sid}", response_model=S.StreamDetail)
def get_stream(sid: int, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    st = _stream(db, company.id, sid)
    occs = db.execute(select(m.Occurrence).where(m.Occurrence.stream_id == sid).order_by(m.Occurrence.date.desc())).scalars().all()
    base = stream_out(st, db, company.fy_start_month).model_dump()
    return S.StreamDetail(**base, occurrences=[S.OccurrenceOut.model_validate(o) for o in occs], amount_history=st.amount_history or [])


@router.post("/companies/{company_id}/streams", response_model=S.StreamOut)
def create_stream(body: S.StreamCreate, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    company_id = company.id
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
    _event(db, company_id, p, "stream_create", st.vendor_name, {"stream_id": st.id, "expected_amount": body.expected_amount, "cycle": body.cycle})
    db.commit()
    db.refresh(st)
    return stream_out(st, db, company.fy_start_month)


@router.patch("/companies/{company_id}/streams/{sid}", response_model=S.StreamOut)
def patch_stream(sid: int, body: S.StreamPatch, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    st = _stream(db, company.id, sid)
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
    _event(db, company.id, p, "patch", st.vendor_name, {"stream_id": st.id, **{k: (v.isoformat() if isinstance(v, date) else v) for k, v in data.items()}})
    db.commit()
    db.refresh(st)
    return stream_out(st, db, company.fy_start_month)


@router.post("/companies/{company_id}/streams/{sid}/mark-paid", response_model=S.StreamOut)
def mark_paid(sid: int, body: S.MarkPaid, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    company_id = company.id
    st = _stream(db, company_id, sid)
    amount = body.amount or st.expected_amount or 0.0
    desc = f"{st.payee_name or st.vendor_name} | marked paid in IT Tracker"
    batch = m.ImportBatch(company_id=company_id, filename="manual", source_kind="manual", rows_imported=1)
    db.add(batch)
    db.flush()
    runner.ingest_rows(db, company, None, batch, [{"date": body.date, "amount": amount, "direction": "debit", "raw_description": desc}], "manual")
    # for manual streams the engine won't rebuild them; roll the due date here
    old_due = st.next_due
    st.last_paid_date = body.date
    st.last_amount = amount
    if st.cycle_months:
        months = int(st.cycle_months)
        if old_due and (old_due - body.date).days >= -15:
            # paid on time or early: keep the usual due day, move one cycle on from the old due date
            st.next_due = old_due + relativedelta(months=months)
            while st.next_due <= body.date:
                st.next_due += relativedelta(months=months)
        else:
            st.next_due = body.date + relativedelta(months=months)
    uf = dict(st.user_fields or {})
    # marking paid confirms the line as it stands: keep its cycle and amount even if the manual date breaks the rhythm
    uf.update(cycle=st.cycle, cycle_months=st.cycle_months, stream_type=st.stream_type, expected_amount=st.expected_amount)
    if st.paid_from:
        uf["paid_from"] = st.paid_from
    # hold this due date until the next real (bank/Tally) payment shows up, then the engine takes over again
    uf["next_due"] = st.next_due.isoformat() if st.next_due else None
    uf["next_due_basis"] = body.date.isoformat()
    st.user_fields, st.is_user_modified, st.confidence = uf, True, 100
    st.occurrences_count = (st.occurrences_count or 0) + 1
    if "manual" not in (st.sources or []):
        st.sources = list(st.sources or []) + ["manual"]
    _recompute_status(st)
    _event(db, company_id, p, "mark_paid", st.vendor_name, {"stream_id": st.id, "date": body.date.isoformat(), "amount": amount})
    db.commit()
    if not st.stream_key.startswith("manual|"):
        # make sure the learned payee maps to this vendor so the manual row joins the same stream on re-run
        if st.vendor_id and st.payee_name:
            db.add(m.VendorAlias(vendor_id=st.vendor_id, pattern=runner.clean_payee(desc), kind="exact", product=st.product, company_id=company_id))
            db.commit()
        runner.run_engine(db, company_id)
        st = db.get(m.Stream, sid) or st
    db.refresh(st)
    return stream_out(st, db, company.fy_start_month)


@router.post("/companies/{company_id}/streams/{sid}/confirm", response_model=S.StreamOut)
def confirm_stream(sid: int, body: S.ConfirmIn, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    company_id = company.id
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
    _event(db, company_id, p, "confirm", st.vendor_name, {"stream_id": st.id, "accept": body.accept})
    db.commit()
    db.refresh(st)
    return stream_out(st, db, company.fy_start_month)


# ---------- questions ----------
@router.get("/companies/{company_id}/questions", response_model=list[S.QuestionOut])
def questions(open: bool = True, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    stmt = select(m.Question).where(m.Question.company_id == company.id)
    if open:
        stmt = stmt.where(m.Question.answered == False)  # noqa: E712
    return db.execute(stmt.order_by(m.Question.id)).scalars().all()


def _question(db: Session, company_id: int, qid: int) -> m.Question:
    q = db.get(m.Question, qid)
    if not q or q.company_id != company_id:
        raise HTTPException(404, "Question not found")
    if q.answered:
        raise HTTPException(400, "Already answered")
    return q


@router.post("/companies/{company_id}/questions/{qid}/answer", response_model=S.AnswerOut)
def answer(qid: int, body: S.AnswerIn, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    q = _question(db, company.id, qid)
    _check_choice(q, body.choice)
    if q.kind == "bundle" and body.choice == "split" and not body.items:
        raise HTTPException(400, "Send items: [{vendor_key, product, amount}] to split this bill")
    _event(db, company.id, p, "answer", q.kind, {"question_id": q.id, "choice": body.choice, "text": body.text})
    st = runner.answer_question(db, q, body.choice, body.text, items=body.items)
    q = db.get(m.Question, qid)
    return S.AnswerOut(question=S.QuestionOut.model_validate(q), stream=stream_out(st, db, company.fy_start_month) if st else None)


def _choice_ok(q: m.Question, choice: str) -> bool:
    """A choice must be one of the question's options; vendor/bundle questions also accept any 'v:<vendor>:<product>'."""
    keys = {o.get("key") for o in (q.options or [])}
    if choice in keys:
        return True
    if q.kind in ("vendor", "bundle"):
        return choice.startswith("v:") or choice in ("other", "not_it", "hardware", "split")
    return False


def _check_choice(q: m.Question, choice: str):
    if not _choice_ok(q, choice):
        raise HTTPException(400, "That answer is not one of the options for this question")


@router.post("/companies/{company_id}/questions/answer-bulk", response_model=S.BulkAnswerOut)
def answer_bulk(body: S.BulkAnswerIn, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    n = 0
    for a in body.answers:
        q = db.get(m.Question, a.question_id)
        if not q or q.company_id != company.id or q.answered:
            continue
        if q.kind == "bundle" and a.choice == "split" and not a.items:
            continue
        if not _choice_ok(q, a.choice):
            continue
        runner.answer_question(db, q, a.choice, a.text, items=a.items, run=False)
        n += 1
    _event(db, company.id, p, "answer_bulk", None, {"answered": n})
    db.commit()
    summary = runner.run_engine(db, company.id)
    return S.BulkAnswerOut(answered=n, engine=S.EngineSummary(**summary))


# ---------- upcoming ----------
def _upcoming(db: Session, company: m.Company, days: int) -> list[dict]:
    today = today_ist()
    end = today + timedelta(days=days)
    streams = db.execute(select(m.Stream).where(m.Stream.company_id == company.id, m.Stream.dismissed == False)).scalars().all()  # noqa: E712
    months: dict[str, dict] = {}
    for s in streams:
        if s.status not in LIVE and not (s.status == "needs_confirm" and s.confidence >= 45):
            continue
        so = None
        for d in due_dates_in_range(s.next_due, s.cycle_months, today - timedelta(days=45), end):
            if d < today and s.status not in ("overdue", "charge_missed"):
                continue
            key = d.strftime("%Y-%m")
            mth = months.setdefault(key, {"month": key, "total": 0.0, "items": []})
            so = so or stream_out(s, db, company.fy_start_month).model_dump()
            item = dict(so)
            item["due"] = d.isoformat()
            mth["items"].append(item)
            mth["total"] += s.expected_amount or 0
    out = sorted(months.values(), key=lambda x: x["month"])
    for mth in out:
        mth["items"].sort(key=lambda i: i["due"])
        mth["total"] = round(mth["total"], 2)
    return out


@router.get("/companies/{company_id}/upcoming")
def upcoming(days: int = 90, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    return _upcoming(db, company, days)


# ---------- export ----------
@router.get("/companies/{company_id}/export.xlsx")
def export_xlsx(company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    from app.export import build_workbook
    streams = [s.model_dump() for s in list_streams(company=company, db=db)]
    data = build_workbook(db, company, streams, _upcoming(db, company, 365))
    fname = re.sub(r"[^A-Za-z0-9]+", "_", company.short_name or company.name).strip("_")[:40] or "it_tracker"
    return RawResponse(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       headers={"Content-Disposition": f'attachment; filename="{fname}_it_tracker.xlsx"'})


# ---------- reminders ----------
@router.get("/companies/{company_id}/reminders", response_model=list[S.ReminderPreview])
def reminders_preview(days: int = 30, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    return R.preview_reminders(db, company, today_ist(), days)


@router.post("/companies/{company_id}/reminders/send-now")
def reminders_send_now(body: S.SendNowIn, company: m.Company = Depends(ACCOUNTANT), p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    st = _stream(db, company.id, body.stream_id)
    chans = R.channels_for(company)
    if not chans:
        raise HTTPException(400, "No channel is set up: add the owner's phone/email and switch WhatsApp or email on in Settings")
    sent = []
    for ch, to in chans:
        row = R.deliver(db, company, st, ch, to)
        sent.append({"channel": ch, "to": to, "ok": row.status == "sent", "status": row.status, "error": row.error})
    _event(db, company.id, p, "reminder_send", st.vendor_name, {"stream_id": st.id, "channels": [c for c, _ in chans]})
    db.commit()
    return {"sent": sent}


@router.get("/companies/{company_id}/reminders/log", response_model=list[S.ReminderLogOut])
def reminders_log(limit: int = 50, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    return db.execute(select(m.ReminderLog).where(m.ReminderLog.company_id == company.id)
                      .order_by(m.ReminderLog.id.desc()).limit(min(limit, 500))).scalars().all()


@router.post("/internal/reminders/run")
def reminders_run(request: Request, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    if not p.is_script and not any(r == "owner" for _, r in auth.companies_for(db, p)):
        raise HTTPException(403, "Owners only")
    return R.run_reminders(db)


# ---------- audit ----------
@router.get("/companies/{company_id}/events", response_model=list[S.EventOut])
def events(limit: int = 100, company: m.Company = Depends(VIEWER), db: Session = Depends(get_db)):
    return db.execute(select(m.Event).where(m.Event.company_id == company.id).order_by(m.Event.id.desc()).limit(min(limit, 1000))).scalars().all()


# ---------- vendors ----------
@router.get("/vendors", response_model=list[S.VendorOut])
def vendors(q: str | None = None, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(m.Vendor).where(m.Vendor.exclude == False).order_by(m.Vendor.name)).scalars().all()  # noqa: E712
    if q:
        rows = [v for v in rows if q.lower() in v.name.lower()]
    return rows


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(func.count(m.Vendor.id)))
    return {"ok": True, "time": datetime.utcnow().isoformat()}
