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
    short_name: str | None = None
    role: str | None = None


class SettingsOut(BaseModel):
    name: str
    gstin: str | None
    fy_start_month: int
    short_name: str | None
    owner_phone: str | None
    owner_email: str | None
    accountant_email: str | None
    whatsapp_enabled: bool
    email_enabled: bool
    reminder_days_before: dict
    weekly_digest_day: str | None


class SettingsPatch(BaseModel):
    name: str | None = None
    gstin: str | None = None
    fy_start_month: int | None = None
    short_name: str | None = None
    owner_phone: str | None = None
    owner_email: str | None = None
    accountant_email: str | None = None
    whatsapp_enabled: bool | None = None
    email_enabled: bool | None = None
    reminder_days_before: dict[str, int] | None = None
    weekly_digest_day: str | None = None


# ---- auth ----
class RegisterIn(BaseModel):
    name: str
    email: str
    password: str
    company_name: str


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str


class CompanyRole(BaseModel):
    id: int
    name: str
    role: str


class MeOut(BaseModel):
    user: UserOut | None
    companies: list[CompanyRole]


class InviteIn(BaseModel):
    company_id: int
    email: str
    role: str = "viewer"
    name: str | None = None


class InviteOut(BaseModel):
    email: str
    temp_password: str | None
    role: str


class AliasOut(BaseModel):
    id: int
    pattern: str
    vendor_name: str
    product: str | None
    created_at: datetime | None
    hidden: bool


class ReminderPreview(BaseModel):
    stream_id: int
    vendor_name: str
    product: str | None
    amount: float | None
    due: str
    days_before: int
    channel: list[str]
    will_send_on: str


class SendNowIn(BaseModel):
    stream_id: int


class ReminderLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stream_id: int | None
    vendor_name: str
    channel: str
    to: str
    sent_at: datetime
    status: str
    message: str
    error: str | None = None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    at: datetime
    user: str
    action: str
    target: str | None
    detail: dict | None


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
    detected_bank: str | None = None
    hint: str | None = None


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
    # v2
    rcm_gst: float | None = None
    quantity: int | None = None
    unit_price: float | None = None
    fy: str | None = None
    flags_human: list[str] = []
    supplier_history: list[str] = []
    change_note: str | None = None


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
    items: list[dict] | None = None   # bundle "split": [{vendor_key, product, amount}]


class BulkAnswerItem(AnswerIn):
    question_id: int


class BulkAnswerIn(BaseModel):
    answers: list[BulkAnswerItem]


class BulkAnswerOut(BaseModel):
    answered: int
    engine: EngineSummary


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
