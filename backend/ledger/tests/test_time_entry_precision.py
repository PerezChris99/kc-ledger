"""Creation and editing use the same financial work-hour precision rules."""

from decimal import Decimal

import pytest
from django.utils import timezone

from ledger.models import Client, Engagement, TimeEntry


@pytest.mark.django_db
def test_time_entry_creation_rejects_fractional_centihours(staff_client):
    owner = Client.objects.create(name="Precision test")
    engagement = Engagement.objects.create(client=owner, name="Review")
    url = "/api/time-entries"
    payload = {
        "engagement_id": engagement.pk,
        "hours": "1.001",
        "category": "billable",
        "started_at": timezone.now().isoformat(),
    }
    denied = staff_client.post(url, data=payload, content_type="application/json")
    assert denied.status_code == 422, denied.content
    assert not TimeEntry.objects.filter(engagement=engagement).exists()

    payload["hours"] = "1.50"
    accepted = staff_client.post(url, data=payload, content_type="application/json")
    assert accepted.status_code == 200, accepted.content
    assert TimeEntry.objects.get(engagement=engagement).hours == Decimal("1.50")
