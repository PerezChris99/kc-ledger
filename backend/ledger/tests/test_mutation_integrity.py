"""Financial mutations must roll back on audit failure and preserve invariants."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from ledger.models import Client, Engagement, Invoice


@pytest.mark.django_db
def test_client_creation_rolls_back_when_audit_write_fails(staff_client):
    with patch("ledger.api.Event.objects.create", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError, match="audit unavailable"):
            staff_client.post(
                "/api/clients",
                data={"name": "Must not persist", "currency": "USD"},
                content_type="application/json",
            )
    assert not Client.objects.filter(name="Must not persist").exists()


@pytest.mark.django_db
def test_invoice_edit_rolls_back_when_audit_write_fails(staff_client):
    owner = Client.objects.create(name="Rollback client")
    invoice = Invoice.objects.create(
        client=owner,
        number="ROLLBACK-001",
        title="Original",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=7),
        amount=Decimal("100.00"),
        currency="USD",
        status=Invoice.Status.SENT,
    )
    with patch("ledger.api.Event.objects.create", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError, match="audit unavailable"):
            staff_client.patch(
                f"/api/invoices/{invoice.pk}",
                data={"title": "Should not persist"},
                content_type="application/json",
            )
    invoice.refresh_from_db()
    assert invoice.title == "Original"


@pytest.mark.django_db
def test_engagement_edit_rejects_invalid_dates_and_recurring_bounds(staff_client):
    owner = Client.objects.create(name="Engagement validation")
    engagement = Engagement.objects.create(
        client=owner,
        name="Valid engagement",
        start_date=date.today(),
        recurring_interval_days=0,
    )
    invalid = [
        {"end_date": (date.today() - timedelta(days=1)).isoformat()},
        {"recurring_interval_days": 366},
        {"recurring_interval_days": -1},
        {"agreed_amount": "5.001"},
    ]
    for patch_values in invalid:
        response = staff_client.patch(
            f"/api/engagements/{engagement.pk}",
            data=patch_values,
            content_type="application/json",
        )
        assert response.status_code == 422, (patch_values, response.content)
    engagement.refresh_from_db()
    assert engagement.end_date is None
    assert engagement.recurring_interval_days == 0
    assert engagement.agreed_amount == Decimal(0)


@pytest.mark.django_db
def test_engagement_create_rejects_money_precision_beyond_cents(staff_client):
    owner = Client.objects.create(name="Precision client")
    response = staff_client.post(
        "/api/engagements",
        data={
            "client_id": owner.pk,
            "name": "Fractional cent",
            "agreed_amount": "12.001",
            "rate": "1.00",
        },
        content_type="application/json",
    )
    assert response.status_code == 422, response.content
    assert not Engagement.objects.filter(client=owner).exists()
