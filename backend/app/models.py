"""SQLAlchemy models.

Pipeline shape:  RawRow (one per line in a file)  ->  Occurrence (one real payment, duplicates merged)
                 ->  Stream (one licence / subscription line, built from repeating occurrences).
Vendor / VendorAlias is the global dictionary; company-scoped aliases are learned from user answers.
Question is the "needs attention" inbox.
"""
from datetime import datetime, date
from sqlalchemy import (Integer, String, Float, Date, DateTime, Boolean, ForeignKey, JSON, Text, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fy_start_month: Mapped[int] = mapped_column(Integer, default=4)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # settings (v2)
    short_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    owner_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)      # E.164, e.g. +919876543210
    owner_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accountant_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_days_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"monthly":5,"quarterly":10,"yearly":30}
    weekly_digest_day: Mapped[str | None] = mapped_column(String(3), nullable=True)  # "mon".."sun" | None


DEFAULT_REMINDER_DAYS = {"monthly": 5, "quarterly": 10, "yearly": 30}


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Membership(Base):
    """Who may open which company, and what they may do there: owner | accountant | viewer."""
    __tablename__ = "memberships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    role: Mapped[str] = mapped_column(String(12), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReminderLog(Base):
    __tablename__ = "reminder_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    stream_id: Mapped[int | None] = mapped_column(ForeignKey("streams.id"), nullable=True, index=True)
    vendor_name: Mapped[str] = mapped_column(String(120))
    due: Mapped[date | None] = mapped_column(Date, nullable=True)
    channel: Mapped[str] = mapped_column(String(12))        # whatsapp | email
    to: Mapped[str] = mapped_column(String(200))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30))         # sent | failed | skipped_not_configured
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Event(Base):
    """Audit trail: who did what on a company (patch / mark-paid / confirm / answer / upload / settings / alias delete)."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped[str] = mapped_column(String(200), default="")
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Account(Base):
    """Where money left from / where rows came from: a bank account, a card, the MD's personal card, a Tally export."""
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))  # bank | card | personal | tally | generic
    bank_name: Mapped[str | None] = mapped_column(String(60), nullable=True)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    source_kind: Mapped[str] = mapped_column(String(20))
    detected_format: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RawRow(Base):
    """One line from a statement / register / invoice, normalised to a common shape."""
    __tablename__ = "raw_rows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(20))  # bank | card | tally | email | gst | manual
    date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Float)              # positive number
    direction: Mapped[str] = mapped_column(String(6))          # debit | credit
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    fx_amount: Mapped[float | None] = mapped_column(Float, nullable=True)  # original foreign amount if known
    raw_description: Mapped[str] = mapped_column(Text)
    payee_clean: Mapped[str] = mapped_column(String(200), index=True)
    payment_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)  # card|upi|neft|rtgs|imps|cheque|cash|si|nach|unknown
    invoice_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    taxable: Mapped[float | None] = mapped_column(Float, nullable=True)
    gst: Mapped[float | None] = mapped_column(Float, nullable=True)
    ledger: Mapped[str | None] = mapped_column(String(120), nullable=True)   # Tally ledger / expense head
    is_personal: Mapped[bool] = mapped_column(Boolean, default=False)
    dedupe_key: Mapped[str] = mapped_column(String(120), index=True)  # avoids importing the same line twice
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Vendor(Base):
    """Global catalogue of software / IT vendors and resellers."""
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    default_cycle: Mapped[str] = mapped_column(String(20), default="monthly")
    variable: Mapped[bool] = mapped_column(Boolean, default=False)      # usage-based amounts
    prepaid: Mapped[bool] = mapped_column(Boolean, default=False)       # credits / top-ups
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    entity_type: Mapped[str] = mapped_column(String(30), default="domestic")  # domestic | foreign_gst | foreign_no_gst
    is_reseller: Mapped[bool] = mapped_column(Boolean, default=False)
    sells: Mapped[list | None] = mapped_column(JSON, nullable=True)    # for resellers: vendor keys they typically sell
    pay_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    exclude: Mapped[bool] = mapped_column(Boolean, default=False)      # bank fees, government, telecom-not-IT etc.
    intro_pricing: Mapped[bool] = mapped_column(Boolean, default=False)


class VendorAlias(Base):
    __tablename__ = "vendor_aliases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    pattern: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10), default="regex")  # regex | exact
    product: Mapped[str | None] = mapped_column(String(120), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)  # None = global


class Occurrence(Base):
    """One real payment / bill, after merging duplicates seen in several sources."""
    __tablename__ = "occurrences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)
    payee_clean: Mapped[str] = mapped_column(String(200))
    product: Mapped[str | None] = mapped_column(String(120), nullable=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    amount_paid: Mapped[float] = mapped_column(Float)
    amount_gross: Mapped[float] = mapped_column(Float)   # what recurrence groups on (invoice total when known)
    taxable: Mapped[float | None] = mapped_column(Float, nullable=True)
    gst: Mapped[float | None] = mapped_column(Float, nullable=True)
    tds: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    fx_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_personal: Mapped[bool] = mapped_column(Boolean, default=False)
    unpaid: Mapped[bool] = mapped_column(Boolean, default=False)        # booked (Tally) but no bank line yet
    sources: Mapped[list] = mapped_column(JSON, default=list)             # ["bank","tally"]
    raw_row_ids: Mapped[list] = mapped_column(JSON, default=list)
    raw_description: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str | None] = mapped_column(String(30), nullable=True)  # alias|reseller|fingerprint|fuzzy|cross|user|none
    stream_id: Mapped[int | None] = mapped_column(ForeignKey("streams.id"), nullable=True, index=True)
    manual: Mapped[bool] = mapped_column(Boolean, default=False)


class Stream(Base):
    """One line on the dashboard: a licence / subscription / AMC / prepaid pool."""
    __tablename__ = "streams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    stream_key: Mapped[str] = mapped_column(String(200), index=True)  # stable across engine re-runs
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    vendor_name: Mapped[str] = mapped_column(String(120))
    payee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="other")
    stream_type: Mapped[str] = mapped_column(String(15), default="subscription")  # subscription|amc|one_time|prepaid
    cycle: Mapped[str] = mapped_column(String(15), default="irregular")
    cycle_months: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    first_seen: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    anchor_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="needs_confirm", index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_from: Mapped[str | None] = mapped_column(String(120), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pay_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reminder_on: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    amount_history: Mapped[list] = mapped_column(JSON, default=list)
    is_user_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    user_fields: Mapped[dict] = mapped_column(JSON, default=dict)   # fields the user set; engine never overwrites these
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # engine extras: rcm_gst, quantity, unit_price, change_note, supplier_history
    occurrences_count: Mapped[int] = mapped_column(Integer, default=0)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(15))  # vendor | cycle | split | stopped | bundle
    key: Mapped[str] = mapped_column(String(200), index=True)  # stable id so re-runs don't duplicate
    prompt: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    options: Mapped[list] = mapped_column(JSON, default=list)
    stream_id: Mapped[int | None] = mapped_column(ForeignKey("streams.id"), nullable=True)
    answered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    answer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index("ix_rawrow_company_dedupe", RawRow.company_id, RawRow.dedupe_key)
