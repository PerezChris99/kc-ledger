from datetime import date
from decimal import Decimal
import pytest
from django.db import IntegrityError
from ledger.models import Client, Invoice

@pytest.mark.django_db
def test_client_score_is_bounded():
    client = Client.objects.create(name="Test Client", score=100)
    assert client.score == 100
    with pytest.raises(IntegrityError):
        Client.objects.create(name="Invalid Score", score=101)

@pytest.mark.django_db
def test_invoice_requires_positive_amount():
    client = Client.objects.create(name="Invoice Client")
    with pytest.raises(IntegrityError):
        Invoice.objects.create(client=client, number="INV-0", title="Invalid", issue_date=date.today(), due_date=date.today(), amount=Decimal("0"))
