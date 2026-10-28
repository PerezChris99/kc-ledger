from datetime import date, timedelta
from decimal import Decimal
import pytest
from ledger.services.instalments import allocate_payment_fifo, evaluate_plan_verdict

TODAY = date(2026, 10, 28)

@pytest.mark.parametrize("amount,expected", [(1, "1.00"), (10, "10.00"), (25, "25.00"), (40, "40.00"), (50, "50.00"), (75, "75.00"), (100, "100.00"), (125, "125.00"), (150, "150.00"), (200, "200.00")])
def test_fifo_allocation_amounts(amount, expected):
    result = allocate_payment_fifo([{"id": 1, "seq": 1, "due_date": date(2026, 1, 1), "amount": Decimal("200"), "allocated": 0}], Decimal(str(amount)))
    assert result["allocations"][0]["amount"] == Decimal(expected)

def test_fifo_splits_across_instalments():
    result = allocate_payment_fifo([
        {"id": 1, "seq": 1, "due_date": date(2026, 1, 1), "amount": "30", "allocated": "10"},
        {"id": 2, "seq": 2, "due_date": date(2026, 2, 1), "amount": "50", "allocated": "0"},
    ], Decimal("50"))
    assert result["allocations"] == [{"instalment_id": 1, "amount": Decimal("20.00")}, {"instalment_id": 2, "amount": Decimal("30.00")}]
    assert result["unallocated"] == Decimal("0.00")

def test_fifo_reports_overpayment():
    result = allocate_payment_fifo([{"id": 1, "due_date": date(2026, 1, 1), "amount": "20"}], Decimal("25"))
    assert result["unallocated"] == Decimal("5.00")

def test_fifo_skips_paid_and_waived():
    result = allocate_payment_fifo([
        {"id": 1, "due_date": date(2026, 1, 1), "amount": "10", "status": "paid"},
        {"id": 2, "due_date": date(2026, 2, 1), "amount": "10", "status": "waived"},
        {"id": 3, "due_date": date(2026, 3, 1), "amount": "10"},
    ], Decimal("10"))
    assert result["allocations"][0]["instalment_id"] == 3

def test_nonpositive_payment_rejected():
    with pytest.raises(ValueError):
        allocate_payment_fifo([], Decimal("0"))

def test_empty_plan_is_in_progress():
    assert evaluate_plan_verdict([], TODAY) == "in_progress"

def test_future_plan_is_in_progress():
    assert evaluate_plan_verdict([{"due_date": TODAY + timedelta(days=10), "amount": "10"}], TODAY) == "in_progress"

def test_due_soon_is_at_risk():
    assert evaluate_plan_verdict([{"due_date": TODAY + timedelta(days=2), "amount": "10"}], TODAY) == "at_risk"

def test_old_unpaid_plan_is_broken():
    assert evaluate_plan_verdict([{"due_date": TODAY - timedelta(days=40), "amount": "10"}], TODAY) == "broken"

def test_paid_on_time_is_perfect():
    assert evaluate_plan_verdict([{"due_date": TODAY, "paid_on": TODAY, "status": "paid"}], TODAY) == "perfect"

def test_paid_late_is_late():
    assert evaluate_plan_verdict([{"due_date": TODAY - timedelta(days=5), "paid_on": TODAY, "status": "paid"}], TODAY) == "late"
