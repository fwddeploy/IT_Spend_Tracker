from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class CompanyIn(BaseModel):
    name: str
    gstin: str | None = None
    fy_start_month: int = 4


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    gstin: str | None
    fy_start_month: int
    created_at: datetime


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    kind: str
    bank_name: str | None = None


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: str
    source_kind: str
    account_label: str | None = None
    rows_imported: int
    rows_skipped: int
    detected_format: str | None
    created_at: datetime
    error: str | None = None


class EngineSummary(BaseModel):
    occurrences: int
    streams: int
    questions_open: int
    auto_accepted: int
    needs_confirm: int
    unclassified: int
    ran_at: str


class UploadOut(BaseModel):
    batch: ImportBatchOut
    engine: EngineSummary


class OccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    amount_paid: float
    amount_gross: float
    taxable: float | None
    gst: float | None
    tds: float | None
    fees: float
    currency: str
    fx_amount: float | None
    payment_mode: str | None
    invoice_no: str | None
    period_from: date | None
    period_to: date | None
    sources: list[str]
    raw_description: str
    unpaid: bool = False


class StreamOut(BaseModel):
    id: int
    vendor_name: str
    payee_name: str | None
    product: str | None
    category: str
    stream_type: str
    cycle: str
    cycle_months: float | None
    expected_amount: float | None
    avg_amount: float | None
    monthly_equivalent: float
    currency: str
    last_paid_date: date | None
    next_due: date | None
    anchor_day: int | None
    status: str
    confidence: int
    auto_renew: bool
    paid_from: str | None
    owner_name: str | None
    pay_url: str | None
    reminder_on: bool
    notes: str | None
    is_user_modified: bool
    occurrences_count: int
    sources: list[str]
    first_seen: date | None
    flags: list[str]


class StreamDetail(StreamOut):
    occurrences: list[OccurrenceOut]
    amount_history: list[dict]


class StreamCreate(BaseModel):
    vendor_name: str
    product: str | None = None
    category: str = "other"
    cycle: str = "yearly"
    expected_amount: float
    next_due: date | None = None
    last_paid_date: date | None = None
    auto_renew: bool = False
    paid_from: str | None = None
    owner_name: str | None = None
    pay_url: str | None = None
    notes: str | None = None


class StreamPatch(BaseModel):
    vendor_name: str | None = None
    product: str | None = None
    category: str | None = None
    cycle: str | None = None
    expected_amount: float | None = None
    next_due: date | None = None
    status: str | None = None
    auto_renew: bool | None = None
    paid_from: str | None = None
    owner_name: str | None = None
    pay_url: str | None = None
    reminder_on: bool | None = None
    notes: str | None = None


class MarkPaid(BaseModel):
    date: date
    amount: float | None = None


class ConfirmIn(BaseModel):
    accept: bool


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    prompt: str
    context: dict
    options: list[dict]
    stream_id: int | None
    answered: bool
    answer: str | None
    created_at: datetime


class AnswerIn(BaseModel):
    choice: str
    text: str | None = None


class AnswerOut(BaseModel):
    question: QuestionOut
    stream: StreamOut | None = None


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    name: str
    category: str
    default_cycle: str
    variable: bool
    is_reseller: bool
