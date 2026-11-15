"""ReportLab portable PDF tests."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from ledger.models import Client, Invoice


@pytest.mark.django_db
def test_invoice_pdf_is_generated_without_native_gtk(staff_client):
    customer = Client.objects.create(name="PDF Customer")
    invoice = Invoice.objects.create(
        client=customer, number="PDF-TEST-123", title="Software development",
        issue_date=date.today(), due_date=date.today() + timedelta(days=14),
        amount=Decimal("120.00"), currency="USD",
    )
    response = staff_client.get(f"/api/invoices/{invoice.pk}/pdf")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_client_dossier_pdf_is_generated(staff_client):
    customer = Client.objects.create(name="Dossier Customer")
    response = staff_client.get(f"/api/clients/{customer.pk}/dossier.pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
