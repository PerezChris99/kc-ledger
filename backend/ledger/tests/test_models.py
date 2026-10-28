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


@pytest.mark.django_db
def test_model_delete_is_soft_delete():
    client = Client.objects.create(name="Archive Me")
    client.delete()
    assert not Client.objects.filter(pk=client.pk).exists()
    assert Client.all_objects.filter(pk=client.pk, deleted_at__isnull=False).exists()

@pytest.mark.django_db
def test_queryset_delete_is_soft_delete():
    client = Client.objects.create(name="Bulk Archive")
    count, _ = Client.objects.filter(pk=client.pk).delete()
    assert count == 1
    assert not Client.objects.filter(pk=client.pk).exists()
    assert Client.all_objects.filter(pk=client.pk, deleted_at__isnull=False).exists()

@pytest.mark.django_db
def test_audit_events_reject_update_and_delete():
    from django.core.exceptions import ValidationError
    from django.utils import timezone
    from ledger.models import Event
    event = Event.objects.create(kind="test_event", category=Event.Category.MONEY, polarity=0,
        title="Immutable", detail="Test", occurred_at=timezone.now())
    event.title = "Changed"
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        Event.objects.filter(pk=event.pk).update(title="Changed")
    with pytest.raises(ValidationError):
        Event.objects.filter(pk=event.pk).delete()
