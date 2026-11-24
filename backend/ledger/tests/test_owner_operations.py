from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from ledger.models import Client, Event, Expense, Instalment, Invoice, Payment


@pytest.mark.django_db
def test_payment_cycle_retries_reversal_and_reconciliation(staff_client, tmp_path):
    today = timezone.localdate()
    client = Client.objects.create(name="Billing acceptance")
    invoice = Invoice.objects.create(
        client=client,
        number="R1",
        amount=100,
        issue_date=today - timedelta(days=10),
        due_date=today,
        status="sent",
    )
    rows = [
        Instalment.objects.create(
            invoice=invoice, client=client, seq=i, label="Milestone", due_date=today, amount=50
        )
        for i in (1, 2)
    ]

    def post(path, data):
        return staff_client.post("/api/" + path, data=data, content_type="application/json")

    first_date = today - timedelta(days=4)
    payload = {
        "invoice_id": invoice.pk,
        "amount": "50",
        "paid_on": str(first_date),
        "submission_key": str(uuid4()),
    }
    first = post("payments", payload)
    assert first.status_code == 200
    assert post("payments", payload).json() == first.json()
    assert post("payments", dict(payload, amount="20")).status_code == 409
    second = post(
        "payments",
        dict(payload, submission_key=str(uuid4()), paid_on=str(today - timedelta(days=2))),
    )
    assert second.status_code == 200
    rows[0].refresh_from_db()
    invoice.refresh_from_db()
    assert rows[0].paid_on == first_date
    assert timezone.localdate(invoice.paid_at) == today - timedelta(days=2)
    path = f"payments/{first.json()['payment_id']}/reverse"
    assert post(path, {"reason": "Wrong invoice"}).status_code == 200
    assert post(path, {"reason": "Wrong invoice"}).status_code == 200
    assert Event.objects.filter(kind="payment_reversed").count() == 1
    assert post("payments", payload).status_code == 409
    assert Payment.objects.count() == 1
    assert Decimal(staff_client.get("/api/invoices").json()["items"][0]["outstanding"]) == 50
    statement = tmp_path / "opening.csv"
    statement.write_text("invoice,currency,outstanding\nR1,USD,50.00\n")
    call_command("reconcile_ledger", str(statement))
    statement.write_text("invoice,currency,outstanding\nR1,USD,99.00\n")
    with pytest.raises(CommandError):
        call_command("reconcile_ledger", str(statement))
    assert post("payments", dict(payload, submission_key=str(uuid4()))).status_code == 200
    invoice.refresh_from_db()
    assert invoice.status == "paid"
    assert staff_client.get(f"/api/invoices/{invoice.pk}/pdf").status_code == 200


@pytest.mark.django_db
def test_dashboard_omits_future_activity(staff_client):
    tomorrow = timezone.localdate() + timedelta(days=1)
    client = Client.objects.create(name="Future")
    Invoice.objects.create(
        client=client, number="future", amount=100, issue_date=tomorrow, due_date=tomorrow
    )
    Expense.objects.create(
        client=client, category="office", amount=15, currency="USD", spent_on=tomorrow
    )
    dashboard = staff_client.get("/api/dashboard").json()
    assert Decimal(dashboard["expenses"]) == Decimal(dashboard["outstanding"]) == 0


@pytest.mark.django_db
def test_owner_password_recovery_invalidates_old_session(client, monkeypatch):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.management.commands.changepassword import Command

    user = get_user_model().objects.create_superuser(
        "recovery-owner", password="Old-Owner-Password-2525"
    )
    client.force_login(user)
    assert client.get("/api/session").json()["authenticated"]
    new = "New-Owner-Password-3026"
    monkeypatch.setattr(Command, "_get_pass", lambda *args: new)
    call_command("changepassword", user.username)
    assert not client.get("/api/session").json()["authenticated"]
    assert client.login(username=user.username, password=new)
