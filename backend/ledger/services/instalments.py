from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable

ZERO = Decimal("0.00")
VERDICT_WEIGHTS = {"perfect": 1.0, "late": 0.5, "in_progress": 0.7, "at_risk": 0.2, "broken": 0.0}


def allocate_payment_fifo(instalments: Iterable[dict[str, Any]], amount: Decimal) -> dict[str, Any]:
    """Allocate a positive payment against unpaid instalment balances in due-date order."""
    remaining = Decimal(str(amount)).quantize(Decimal("0.01"))
    if remaining <= ZERO:
        raise ValueError("Payment amount must be positive.")
    rows = sorted(instalments, key=lambda row: (row["due_date"], row.get("seq", 0), str(row.get("id", ""))))
    allocations = []
    for row in rows:
        if row.get("status") in {"paid", "waived"}:
            continue
        scheduled = Decimal(str(row["amount"]))
        already_paid = Decimal(str(row.get("allocated", "0")))
        balance = max(ZERO, scheduled - already_paid)
        allocated = min(balance, remaining)
        if allocated > ZERO:
            allocations.append({"instalment_id": row.get("id"), "amount": allocated.quantize(Decimal("0.01"))})
            remaining -= allocated
        if remaining <= ZERO:
            break
    return {"allocations": allocations, "unallocated": remaining.quantize(Decimal("0.01"))}


def evaluate_plan_verdict(instalments: Iterable[dict[str, Any]], as_of: date | None = None) -> str:
    """Return the five-state plan verdict using paid dates, due dates and grace periods."""
    today = as_of or date.today()
    rows = list(instalments)
    if not rows:
        return "in_progress"

    unresolved = []
    settled_late = False
    for row in rows:
        status = row.get("status", "pending")
        due = row["due_date"]
        grace = int(row.get("grace_days", 0))
        paid_on = row.get("paid_on")
        if status == "waived":
            continue
        if status == "paid" or paid_on:
            paid_date = paid_on
            if paid_date and paid_date > due + timedelta(days=grace):
                settled_late = True
            continue
        if status == "missed":
            return "broken" if today > due + timedelta(days=grace + 30) else "at_risk"
        if today > due + timedelta(days=grace + 30):
            return "broken"
        if today > due + timedelta(days=grace):
            unresolved.append("overdue")
        elif today >= due - timedelta(days=3):
            unresolved.append("due_soon")
        else:
            unresolved.append("future")

    if not unresolved:
        return "late" if settled_late else "perfect"
    if "overdue" in unresolved or "due_soon" in unresolved:
        return "at_risk"
    return "in_progress"
