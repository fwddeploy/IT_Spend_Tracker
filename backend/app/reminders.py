"""Reminders: which lines need a nudge today, and sending it over WhatsApp (Meta Cloud API) / email (SMTP).

Rules (docs/API-v2-additions.md):
* a line with `reminder_on` is reminded when `next_due - today` equals the company's days_before for its cycle
  (monthly 5 / quarterly 10 / yearly 30 by default), or when it is overdue and hasn't been reminded in 7 days;
* one message per stream + due date + channel + recipient (dedupe via reminder_log);
* if the channel env vars are missing the attempt is logged as `skipped_not_configured` so the UI can say so.
"""
from __future__ import annotations
import logging
import os
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy import select, text as sa_text
from sqlalchemy.orm import Session

from app import models as m
from app.engine.runner import today_ist

log = logging.getLogger("ittracker.reminders")
LIVE = ("active", "due_soon", "overdue", "charge_missed")
OVERDUE_REPEAT_DAYS = 7


# ---------- what to send ----------
def _bucket(cycle_months: float | None) -> str:
    if not cycle_months or cycle_months <= 1:
        return "monthly"
    if cycle_months <= 3:
        return "quarterly"
    return "yearly"


def days_before_for(company: m.Company, stream: m.Stream) -> int:
    cfg = {**m.DEFAULT_REMINDER_DAYS, **(company.reminder_days_before or {})}
    return int(cfg.get(_bucket(stream.cycle_months), 5))


def channels_for(company: m.Company) -> list[tuple[str, str]]:
    """[(channel, to)] configured on the company — not whether env is set (that decides the send status)."""
    out: list[tuple[str, str]] = []
    if company.whatsapp_enabled and company.owner_phone:
        out.append(("whatsapp", company.owner_phone))
    if company.email_enabled:
        for e in (company.owner_email, company.accountant_email):
            if e and ("email", e) not in out:
                out.append(("email", e))
    return out


def _amount(x: float | None) -> str:
    return f"{(x or 0):,.0f}"


def message_for(company: m.Company, st: m.Stream, today: date) -> str:
    days = (st.next_due - today).days if st.next_due else 0
    due_txt = st.next_due.strftime("%d %b %Y") if st.next_due else "-"
    return (f"IT Tracker · {company.short_name or company.name}\n"
            f"{st.vendor_name} – {st.product or ''}\n"
            f"₹{_amount(st.expected_amount)} due {due_txt} ({days} days)\n"
            f"Pay: {st.pay_url or 'ask accountant'}\n"
            f"Reply PAID when done.")


def _candidate_streams(db: Session, company: m.Company) -> list[m.Stream]:
    return db.execute(select(m.Stream).where(m.Stream.company_id == company.id, m.Stream.reminder_on == True,  # noqa: E712
                                             m.Stream.dismissed == False, m.Stream.status.in_(LIVE),  # noqa: E712
                                             m.Stream.next_due != None)).scalars().all()  # noqa: E711


def preview_reminders(db: Session, company: m.Company, today: date, days: int = 30) -> list[dict]:
    """What would go out in the next `days` days (for the settings page)."""
    chans = [c for c, _ in channels_for(company)]
    out = []
    for st in _candidate_streams(db, company):
        db_ = days_before_for(company, st)
        send_on = st.next_due - timedelta(days=db_)
        if send_on < today:
            send_on = today   # window already passed (or overdue): goes out on the next run
        if (send_on - today).days > days:
            continue
        out.append({"stream_id": st.id, "vendor_name": st.vendor_name, "product": st.product, "amount": st.expected_amount,
                    "due": st.next_due.isoformat(), "days_before": db_, "channel": sorted(set(chans)), "will_send_on": send_on.isoformat()})
    out.sort(key=lambda r: (r["will_send_on"], r["due"]))
    return out


def _already_sent(db: Session, st: m.Stream, channel: str, to: str, since: datetime | None = None) -> bool:
    q = select(m.ReminderLog.id).where(m.ReminderLog.stream_id == st.id, m.ReminderLog.channel == channel, m.ReminderLog.to == to,
                                       m.ReminderLog.status != "failed")
    q = q.where(m.ReminderLog.sent_at >= since) if since else q.where(m.ReminderLog.due == st.next_due)
    return db.execute(q.limit(1)).first() is not None


def compute_due_reminders(db: Session, company: m.Company, today: date) -> list[tuple[m.Stream, str, str]]:
    """[(stream, channel, to)] that should be sent right now (dedupe already applied)."""
    chans = channels_for(company)
    if not chans:
        return []
    out = []
    for st in _candidate_streams(db, company):
        gap = (st.next_due - today).days
        if gap == days_before_for(company, st):
            for ch, to in chans:
                if not _already_sent(db, st, ch, to):
                    out.append((st, ch, to))
        elif gap < 0:
            since = datetime.utcnow() - timedelta(days=OVERDUE_REPEAT_DAYS)
            for ch, to in chans:
                if not _already_sent(db, st, ch, to, since=since):
                    out.append((st, ch, to))
    return out


# ---------- senders ----------
def send_whatsapp(to: str, text: str) -> dict:
    phone_id, token = os.environ.get("WA_PHONE_NUMBER_ID"), os.environ.get("WA_TOKEN")
    if not phone_id or not token:
        return {"ok": False, "status": "skipped_not_configured", "error": "WA_PHONE_NUMBER_ID / WA_TOKEN not set"}
    template = os.environ.get("WA_TEMPLATE_NAME")
    to_num = to.lstrip("+").replace(" ", "")
    if template:
        payload = {"messaging_product": "whatsapp", "to": to_num, "type": "template",
                   "template": {"name": template, "language": {"code": os.environ.get("WA_TEMPLATE_LANG", "en")},
                                "components": [{"type": "body", "parameters": [{"type": "text", "text": text}]}]}}
    else:
        payload = {"messaging_product": "whatsapp", "to": to_num, "type": "text", "text": {"body": text}}
    url = f"https://graph.facebook.com/{os.environ.get('WA_API_VERSION', 'v20.0')}/{phone_id}/messages"
    try:
        r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if r.status_code >= 300:
            return {"ok": False, "status": "failed", "error": f"{r.status_code}: {r.text[:300]}"}
        return {"ok": True, "status": "sent"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "error": str(e)[:300]}


def send_email(to: str, subject: str, text: str) -> dict:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return {"ok": False, "status": "skipped_not_configured", "error": "SMTP_HOST not set"}
    port = int(os.environ.get("SMTP_PORT", "587"))
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    sender = os.environ.get("SMTP_FROM") or user or "it-tracker@localhost"
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg.set_content(text)
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            server.ehlo()
            if port == 587:
                server.starttls()
        with server:
            if user and pw:
                server.login(user, pw)
            server.send_message(msg)
        return {"ok": True, "status": "sent"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "failed", "error": str(e)[:300]}


def deliver(db: Session, company: m.Company, st: m.Stream, channel: str, to: str, today: date | None = None) -> m.ReminderLog:
    today = today or today_ist()
    text = message_for(company, st, today)
    if channel == "whatsapp":
        res = send_whatsapp(to, text)
    else:
        res = send_email(to, f"IT Tracker: {st.vendor_name} due {st.next_due.strftime('%d %b') if st.next_due else ''}", text)
    row = m.ReminderLog(company_id=company.id, stream_id=st.id, vendor_name=st.vendor_name, due=st.next_due, channel=channel, to=to,
                        status=res["status"], message=text, error=res.get("error"))
    db.add(row)
    db.flush()
    log.info("reminder company_id=%s stream=%s channel=%s to=%s status=%s", company.id, st.id, channel, to, res["status"])
    return row


def run_reminders(db: Session, today: date | None = None) -> dict:
    """Called hourly by the scheduler and by POST /api/internal/reminders/run."""
    today = today or today_ist()
    sent = skipped = failed = 0
    pg = db.bind is not None and db.bind.dialect.name == "postgresql"
    if pg:   # several uvicorn workers each run the hourly job; only one may send at a time
        if not db.execute(sa_text("SELECT pg_try_advisory_lock(424242)")).scalar():
            return {"sent": 0, "skipped": 0, "failed": 0, "ran_at": datetime.utcnow().isoformat(), "note": "another worker is running reminders"}
    try:
        for company in db.execute(select(m.Company)).scalars().all():
            if not channels_for(company):
                continue
            for st, ch, to in compute_due_reminders(db, company, today):
                row = deliver(db, company, st, ch, to, today)
                if row.status == "sent":
                    sent += 1
                elif row.status == "failed":
                    failed += 1
                else:
                    skipped += 1
            db.commit()
    finally:
        if pg:
            db.execute(sa_text("SELECT pg_advisory_unlock(424242)"))
            db.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed, "ran_at": datetime.utcnow().isoformat()}
