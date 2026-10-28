from datetime import date, timedelta
from decimal import Decimal
import pytest
from ledger.services.instalments import allocate_payment_fifo, evaluate_plan_verdict

TODAY = date(2026, 10, 28)

@pytest.mark.parametrize("amount,expected", [(1,"1.00"),(10,"10.00"),(25,"25.00"),(40,"40.00"),(50,"50.00"),(75,"75.00"),(100,"100.00"),(125,"125.00"),(150,"150.00"),(200,"200.00")])
def test_fifo_allocation_amounts(amount, expected):
    result = allocate_payment_fifo([{"id":1,"seq":1,"due_date":date(2026,1,1),"amount":Decimal("200"),"allocated":0}], Decimal(str(amount)))
    assert result["allocations"][0]["amount"] == Decimal(expected)

@pytest.mark.parametrize("amount", ["0.01","1","4.25","9.99","10","15.75","25","49.50","75","99.99"])
def test_partial_payment_is_allocated_without_exceeding_balance(amount):
    result = allocate_payment_fifo([{"id":9,"seq":1,"due_date":date(2026,1,1),"amount":"100","allocated":"0"}], Decimal(amount))
    assert result["allocations"][0]["amount"] == Decimal(amount).quantize(Decimal("0.01"))
    assert result["unallocated"] == Decimal("0.00")

@pytest.mark.parametrize("amount", ["0","-1","-10.25"])
def test_nonpositive_payment_rejected(amount):
    with pytest.raises(ValueError):
        allocate_payment_fifo([], Decimal(amount))

def test_fifo_splits_across_instalments():
    result = allocate_payment_fifo([
        {"id":1,"seq":1,"due_date":date(2026,1,1),"amount":"30","allocated":"10"},
        {"id":2,"seq":2,"due_date":date(2026,2,1),"amount":"50","allocated":"0"},
    ], Decimal("50"))
    assert result["allocations"] == [{"instalment_id":1,"amount":Decimal("20.00")},{"instalment_id":2,"amount":Decimal("30.00")}]
    assert result["unallocated"] == Decimal("0.00")

def test_fifo_reports_overpayment():
    result = allocate_payment_fifo([{"id":1,"due_date":date(2026,1,1),"amount":"20"}], Decimal("25"))
    assert result["unallocated"] == Decimal("5.00")

def test_fifo_skips_paid_and_waived():
    result = allocate_payment_fifo([
        {"id":1,"due_date":date(2026,1,1),"amount":"10","status":"paid"},
        {"id":2,"due_date":date(2026,2,1),"amount":"10","status":"waived"},
        {"id":3,"due_date":date(2026,3,1),"amount":"10"},
    ], Decimal("10"))
    assert result["allocations"][0]["instalment_id"] == 3

def test_fifo_orders_by_due_date_not_input_order():
    result = allocate_payment_fifo([
        {"id":2,"seq":2,"due_date":date(2026,2,1),"amount":"10"},
        {"id":1,"seq":1,"due_date":date(2026,1,1),"amount":"10"},
    ], Decimal("10"))
    assert result["allocations"][0]["instalment_id"] == 1

def test_fifo_respects_existing_allocation():
    result = allocate_payment_fifo([{"id":1,"due_date":date(2026,1,1),"amount":"10","allocated":"8"}], Decimal("5"))
    assert result["allocations"][0]["amount"] == Decimal("2.00")
    assert result["unallocated"] == Decimal("3.00")

def test_empty_plan_is_in_progress():
    assert evaluate_plan_verdict([], TODAY) == "in_progress"

@pytest.mark.parametrize("days,expected", [(4,"in_progress"),(3,"at_risk"),(2,"at_risk"),(1,"at_risk"),(0,"at_risk"),(-1,"at_risk"),(-10,"at_risk"),(-29,"at_risk"),(-30,"at_risk"),(-31,"broken")])
def test_unpaid_plan_due_date_boundaries(days, expected):
    assert evaluate_plan_verdict([{"due_date":TODAY+timedelta(days=days),"amount":"10","grace_days":0}], TODAY) == expected

@pytest.mark.parametrize("days_late,expected", [(0,"perfect"),(1,"late"),(2,"late"),(3,"late"),(7,"late"),(30,"late")])
def test_settled_plan_grace_period_boundaries(days_late, expected):
    due=TODAY-timedelta(days=days_late)
    assert evaluate_plan_verdict([{"due_date":due,"paid_on":TODAY,"status":"paid","grace_days":0}], TODAY) == expected

def test_paid_within_grace_period_is_perfect():
    assert evaluate_plan_verdict([{"due_date":TODAY-timedelta(days=2),"paid_on":TODAY,"status":"paid","grace_days":2}], TODAY) == "perfect"

def test_old_unpaid_plan_is_broken():
    assert evaluate_plan_verdict([{"due_date":TODAY-timedelta(days=40),"amount":"10"}], TODAY) == "broken"

def test_paid_on_time_is_perfect():
    assert evaluate_plan_verdict([{"due_date":TODAY,"paid_on":TODAY,"status":"paid"}], TODAY) == "perfect"

def test_paid_late_is_late():
    assert evaluate_plan_verdict([{"due_date":TODAY-timedelta(days=5),"paid_on":TODAY,"status":"paid"}], TODAY) == "late"
