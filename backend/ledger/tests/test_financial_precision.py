"""Money cannot be silently rounded during persistence."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from ledger.models import Client, Invoice, Payment


@pytest.mark.django_db
def test_invoice_rejects_millisecond_style_money_precision(staff_client):
    client = Client.objects.create(name="Precision Test")
    response = staff_client.post(
        "/api/invoices",
        data={
            "client_id": client.id,
            "number": "PREC-1",
            "title": "Precise invoice",
            "issue_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=7)).isoformat(),
            "amount": "12.345",
            "currency": "USD",
            "status": "sent",
        },
        content_type="application/json",
    )
    assert response.status_code == 422
    assert not Invoice.objects.filter(number="PREC-1").exists()


@pytest.mark.django_db
def test_payment_rejects_subcent_and_keeps_balances_intact(staff_client):
    client = Client.objects.create(name="Pay Precision Test")
    invoice = Invoice.objects.create(
        client=client,
        number="PREC-PAY-1",
        title="Test",
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=7),
        amount=Decimal("12.00"),
        currency="USD",
    )
    response = staff_client.post(
        "/api/payments",
        data={
            "invoice_id": invoice.id,
            "amount": "0.005",
            "paid_on": date.today().isoformat(),
        },
        content_type="application/json",
    )
    assert response.status_code == 422
    assert not Payment.objects.filter(invoice=invoice).exists()
