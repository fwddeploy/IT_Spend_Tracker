"""Status of a stream on a given day, and the two headline totals."""
from __future__ import annotations
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from app.engine.recurrence import CYCLE_MONTHS, GRACE_DAYS, DUE_SOON_DAYS


def compute_status(*, stream_type: str, cycle: str, cycle_months: float | None, next_due: date | None,
                   last_paid_date: date | None, auto_renew: bool, confidence: int, is_user_modified: bool,
                   dismissed: bool, cancelled: bool, today: date | None = None) -> str:
    today = today or date.today()
    if dismissed:
        return "dismissed"
    if cancelled:
        return "cancelled"
    if stream_type == "one_time":
        return "one_time"
    if stream_type == "prepaid":
        return "active"
    if confidence < 75 and not is_user_modified:
        return "needs_confirm"
    if not next_due or not cycle_months:
        return "active"
    grace = GRACE_DAYS.get(cycle, 15)
    due_soon = DUE_SOON_DAYS.get(cycle, 10)
    days_to_due = (next_due - today).days
    if days_to_due >= 0:
        return "due_soon" if days_to_due <= due_soon else "active"
    overdue_days = -days_to_due
    # stopped: one full extra cycle after due (+ grace)
    stop_after = int(cycle_months * 30.4) + grace
    if overdue_days > stop_after:
        return "amc_lapsed" if stream_type == "amc" else "stopped"
    if overdue_days > grace:
        return "charge_missed" if auto_renew else "overdue"
    return "due_soon"


def due_dates_in_range(next_due: date | None, cycle_months: float | None, start: date, end: date) -> list[date]:
    """All due dates of a stream falling in [start, end]. Rolls forward from next_due; also rolls backwards
    if next_due is already past the range start (an overdue item still counts as cash out this month)."""
    if not next_due or not cycle_months:
        return []
    months = int(cycle_months) if float(cycle_months).is_integer() else None
    out = []
    d = next_due
    # if next_due is before start, walk forward
    guard = 0
    while d < start and guard < 120:
        d = d + relativedelta(months=months) if months else d + timedelta(days=int(cycle_months * 30.4))
        guard += 1
    while d <= end and guard < 240:
        out.append(d)
        d = d + relativedelta(months=months) if months else d + timedelta(days=int(cycle_months * 30.4))
        guard += 1
    return out


def monthly_equivalent(expected_amount: float | None, cycle_months: float | None, stream_type: str) -> float:
    if not expected_amount:
        return 0.0
    if stream_type == "one_time":
        return 0.0
    if stream_type == "prepaid" or not cycle_months:
        return float(expected_amount)  # prepaid: expected already = monthly run-rate
    return float(expected_amount) / float(cycle_months)
