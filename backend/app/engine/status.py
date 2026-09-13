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
    if not next_due:
        return "active"
    grace = GRACE_DAYS.get(cycle, 15)
    due_soon = DUE_SOON_DAYS.get(cycle, 10)
    days_to_due = (next_due - today).days
    if days_to_due >= 0:
        return "due_soon" if days_to_due <= due_soon else "active"
    overdue_days = -days_to_due
    # stopped: one full extra cycle after due (+ grace). A due date with no known cycle still goes overdue;
    # it is called stopped after a year.
    stop_after = int((cycle_months or 12) * 30.4) + grace
    if overdue_days > stop_after:
        return "amc_lapsed" if stream_type == "amc" else "stopped"
    if overdue_days > grace:
        return "charge_missed" if auto_renew else "overdue"
    return "due_soon"


def _nth_due(next_due: date, cycle_months: float, k: int) -> date:
    """k-th due date after next_due. Whole months step with relativedelta from the ORIGINAL date each time,
    so an anchor on the 31st gives 31 Jan, 28 Feb, 31 Mar (not 28 Mar forever); fractional cycles step in days."""
    if float(cycle_months).is_integer():
        return next_due + relativedelta(months=int(cycle_months) * k)
    return next_due + timedelta(days=int(cycle_months * 30.4) * k)


def due_dates_in_range(next_due: date | None, cycle_months: float | None, start: date, end: date) -> list[date]:
    """All due dates of a stream falling in [start, end]. Rolls forward from next_due; also rolls forward
    over the past if next_due is already before the range start (an overdue item still counts as cash out this month)."""
    if not next_due or not cycle_months or cycle_months <= 0 or end < start:
        return []
    # jump straight to the first k with due >= start instead of walking one cycle at a time (a next_due many
    # years in the past must not exhaust a step guard and then leak dates that are before the range)
    k = 0
    if next_due < start:
        approx_days = cycle_months * 30.4
        k = max(0, int((start - next_due).days / approx_days) - 1)
        while _nth_due(next_due, cycle_months, k) < start:
            k += 1
        while k > 0 and _nth_due(next_due, cycle_months, k - 1) >= start:
            k -= 1
    out = []
    guard = 0
    d = _nth_due(next_due, cycle_months, k)
    while d <= end and guard < 240:
        if d >= start:
            out.append(d)
        k += 1
        guard += 1
        d = _nth_due(next_due, cycle_months, k)
    return out


def monthly_equivalent(expected_amount: float | None, cycle_months: float | None, stream_type: str) -> float:
    if not expected_amount:
        return 0.0
    if stream_type == "one_time":
        return 0.0
    if stream_type == "prepaid" or not cycle_months:
        return float(expected_amount)  # prepaid: expected already = monthly run-rate
    return float(expected_amount) / float(cycle_months)
