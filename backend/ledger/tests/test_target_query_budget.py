"""Revenue target performance and currency correctness regressions."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from ledger.models import Client, FxRate, Invoice, Payment, Target


@pytest.mark.django_db
def test_revenue_target_groups_payment_totals_by_currency(staff_client):
    customer = Client.objects.create(name="Target performance client")
    FxRate.objects.create(
        base="USD",
        quote="UGX",
        rate=Decimal(3700),
        fetched_at=timezone.now(),
        source="test",
    )
    invoice = Invoice.objects.create(
        client=customer,
        number="TARGET-PERF-001",
        title="Converted revenue",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        amount=Decimal(370000),
        currency="UGX",
        status=Invoice.Status.PARTIAL,
    )
    for idx in range(50):
        Payment.objects.create(
            invoice=invoice,
            client=customer,
            amount=Decimal("3700.00"),
            paid_on=date.today(),
            reference=f"R-{idx}",
        )
    Target.objects.create(
        name="Revenue target",
        type=Target.Type.REVENUE,
        amount=Decimal("200.00"),
        currency="USD",
        deadline=date.today() + timedelta(days=30),
    )
    with CaptureQueriesContext(connection) as queries:
        response = staff_client.get("/api/targets")
    assert response.status_code == 200, response.content
    row = response.json()["items"][0]
    assert Decimal(row["current"]) == Decimal("50.00")
    assert row["conversion_available"] is True
    assert sum("ledger_payment" in q["sql"].lower() for q in queries) <= 1
    assert sum("ledger_fxrate" in q["sql"].lower() for q in queries) <= 1

    FxRate.objects.all().delete()
    missing = staff_client.get("/api/targets")
    assert missing.status_code == 200
    assert missing.json()["items"][0]["pace_status"] == "fx_missing"
    assert Decimal(missing.json()["items"][0]["current"]) == 0
