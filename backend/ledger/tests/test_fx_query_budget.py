"""Currency conversion uses bounded database queries at the hot paths."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from ledger.models import Client, FxRate, Invoice
from ledger.services.fx import conversion_for


@pytest.mark.django_db
def test_fx_converter_uses_single_query_for_many_values():
    FxRate.objects.create(base="USD", quote="UGX", rate=Decimal("3700"))
    with CaptureQueriesContext(connection) as queries:
        convert = conversion_for("USD")
        amounts = [convert(Decimal("3700"), "UGX") for _ in range(80)]
    assert all(amount == Decimal("1") for amount in amounts)
    assert len(queries) == 1


@pytest.mark.django_db
def test_dashboard_fx_queries_are_independent_of_invoice_count(staff_client):
    FxRate.objects.create(base="USD", quote="UGX", rate=Decimal("3700"))
    customer = Client.objects.create(name="FX load test")
    for number in range(25):
        Invoice.objects.create(
            client=customer, number=f"FX-{number}", title="FX workload",
            amount=Decimal("500.00"), currency="UGX",
            issue_date=date.today(), due_date=date.today() + timedelta(days=10),
        )
    with CaptureQueriesContext(connection) as queries:
        response = staff_client.get("/api/dashboard")
    assert response.status_code == 200
    fx_queries = [q for q in queries if "ledger_fxrate" in q["sql"].lower()]
    assert len(fx_queries) <= 2
