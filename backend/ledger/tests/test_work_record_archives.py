"""Editing, archiving and restoring work records changes live totals safely."""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from ledger.models import Client, Engagement, Event, Expense, TimeEntry


@pytest.mark.django_db
def test_expense_replace_archive_and_restore(staff_client):
    customer = Client.objects.create(name="Expense Archive Client")
    expense = Expense.objects.create(
        client=customer,
        category="Travel",
        amount=Decimal("40.00"),
        currency="USD",
        spent_on=date.today(),
    )
    response = staff_client.put(
        f"/api/expenses/{expense.id}",
        data={
            "client_id": customer.id,
            "engagement_id": None,
            "category": "Equipment",
            "amount": "70.00",
            "currency": "USD",
            "spent_on": date.today().isoformat(),
            "billable": False,
            "note": "Updated",
        },
        content_type="application/json",
    )
    assert response.status_code == 200, response.content
    expense.refresh_from_db()
    assert expense.amount == Decimal("70.00")
    removed = staff_client.delete(f"/api/expenses/{expense.id}")
    assert removed.status_code == 200
    assert not Expense.objects.filter(pk=expense.id).exists()
    assert Expense.all_objects.filter(pk=expense.id, deleted_at__isnull=False).exists()
    restored = staff_client.post(f"/api/archived-records/expense/{expense.id}/restore")
    assert restored.status_code == 200
    assert Expense.objects.filter(pk=expense.id).exists()
    assert Event.objects.filter(kind="expense_restored").exists()


@pytest.mark.django_db
def test_time_entry_replace_archive_and_restore(staff_client):
    customer = Client.objects.create(name="Time Archive Client")
    engagement = Engagement.objects.create(client=customer, name="Client app")
    entry = TimeEntry.objects.create(
        client=customer,
        engagement=engagement,
        hours=Decimal("2.00"),
        category="billable",
        started_at=timezone.now(),
    )
    changed = staff_client.put(
        f"/api/time-entries/{entry.id}",
        data={
            "engagement_id": engagement.id,
            "hours": "3.50",
            "category": "meeting",
            "started_at": timezone.now().isoformat(),
            "note": "Kickoff meeting",
        },
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content
    entry.refresh_from_db()
    assert entry.hours == Decimal("3.50")
    archived = staff_client.delete(f"/api/time-entries/{entry.id}")
    assert archived.status_code == 200
    assert not TimeEntry.objects.filter(pk=entry.id).exists()
    restored = staff_client.post(f"/api/archived-records/time-entry/{entry.id}/restore")
    assert restored.status_code == 200
    assert TimeEntry.objects.filter(pk=entry.id).exists()


@pytest.mark.django_db
def test_engagement_archive_restore_preserves_related_time(staff_client):
    customer = Client.objects.create(name="Engagement Archive Client")
    engagement = Engagement.objects.create(client=customer, name="Infrastructure")
    row = TimeEntry.objects.create(
        client=customer,
        engagement=engagement,
        hours=Decimal("1.25"),
        category="billable",
        started_at=timezone.now(),
    )
    assert staff_client.delete(f"/api/engagements/{engagement.id}").status_code == 200
    assert Engagement.objects.filter(pk=engagement.id).count() == 0
    assert TimeEntry.objects.filter(pk=row.id).exists()
    assert (
        staff_client.post(f"/api/archived-records/engagement/{engagement.id}/restore").status_code
        == 200
    )
    assert Engagement.objects.filter(pk=engagement.id).exists()
