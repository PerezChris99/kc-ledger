"""Background job idempotency, scheduler lifecycle and FX-provider failure paths."""

import io
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from ledger.jobs import (
    draft_recurring_invoices,
    emit_due_reminders,
    refresh_fx_rates,
)
from ledger.models import Client, Engagement, Event, FxRate, Invoice


@pytest.mark.django_db
def test_recurring_draft_is_idempotent_same_day():
    client = Client.objects.create(name="Retainer Scheduler Client")
    Engagement.objects.create(
        client=client,
        name="Monthly application support",
        kind=Engagement.Kind.RETAINER,
        status=Engagement.Status.ACTIVE,
        agreed_amount=Decimal("200.00"),
        currency="USD",
        recurring_interval_days=30,
        next_invoice_date=timezone.localdate(),
    )
    draft_recurring_invoices()
    draft_recurring_invoices()
    invoices = Invoice.objects.filter(client=client)
    assert invoices.count() == 1
    assert invoices.first().status == Invoice.Status.DRAFT
    assert Event.objects.filter(client=client, kind="recurring_invoice_drafted").count() == 1


@pytest.mark.django_db
def test_reminder_job_does_not_duplicate_daily_audit_events():
    client = Client.objects.create(name="Overdue Job Client")
    invoice = Invoice.objects.create(
        client=client,
        number="REMINDER-101",
        title="Overdue invoice",
        issue_date=timezone.localdate() - timedelta(days=40),
        due_date=timezone.localdate() - timedelta(days=15),
        amount=Decimal("100.00"),
        currency="USD",
        status=Invoice.Status.SENT,
    )
    emit_due_reminders()
    emit_due_reminders()
    assert Event.objects.filter(invoice=invoice, kind="invoice_overdue_reminder").count() == 1


@pytest.mark.django_db
def test_fx_refresh_retains_rates_after_failed_provider_response(monkeypatch):
    existing = FxRate.objects.create(
        base="USD",
        quote="UGX",
        rate=Decimal(3600),
        fetched_at=timezone.now(),
        source="manual",
    )
    monkeypatch.setenv("EXCHANGERATE_HOST_ACCESS_KEY", "test-secret-placeholder")

    class FailedResponse:
        def __enter__(self):
            return io.BytesIO(json.dumps({"success": False}).encode())

        def __exit__(self, *_args):
            return False

    with patch("ledger.jobs.urlopen", return_value=FailedResponse()):
        refresh_fx_rates()
    existing.refresh_from_db()
    assert existing.rate == Decimal(3600)
    assert existing.source == "manual"


@pytest.mark.django_db
def test_fx_refresh_rejects_network_failure_without_destroying_rates(monkeypatch):
    existing = FxRate.objects.create(
        base="USD",
        quote="UGX",
        rate=Decimal(3650),
        fetched_at=timezone.now(),
        source="manual",
    )
    monkeypatch.setenv("EXCHANGERATE_HOST_ACCESS_KEY", "test-secret-placeholder")
    with patch("ledger.jobs.urlopen", side_effect=TimeoutError("Synthetic network timeout")):
        refresh_fx_rates()
    existing.refresh_from_db()
    assert existing.rate == Decimal(3650)


@pytest.mark.django_db
def test_overdue_reminder_refreshes_stored_client_score():
    client = Client.objects.create(name="Daily Risk Refresh", score=50)
    Invoice.objects.create(
        client=client, number="DUE-REFRESH-1", title="Past due services",
        issue_date=timezone.localdate() - timedelta(days=20),
        due_date=timezone.localdate() - timedelta(days=10),
        amount=Decimal("250.00"), status=Invoice.Status.SENT,
    )
    emit_due_reminders()
    client.refresh_from_db()
    assert client.score_updated_at is not None
    assert client.score < 50
