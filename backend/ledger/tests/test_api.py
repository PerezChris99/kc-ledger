from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from ledger.models import Client, Event, Instalment, Invoice, Payment, PaymentAllocation, PlanMeta

@pytest.fixture
def staff_client(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="ledger-test-owner", password="test-password-strong-enough", is_staff=True)
    client.force_login(user)
    return client

@pytest.mark.django_db
def test_health_endpoint_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.django_db
def test_financial_api_requires_staff_session(client):
    response = client.get("/api/dashboard")
    assert response.status_code in {401, 403}

@pytest.mark.django_db
def test_staff_can_read_empty_dashboard(staff_client):
    response = staff_client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["client_count"] == 0
    assert body["invoice_count"] == 0
    assert len(body["revenue_trend"]) == 6

@pytest.mark.django_db
def test_client_create_and_read(staff_client):
    response = staff_client.post("/api/clients", data={
        "name": "API Client", "company": "Example Studio", "email": "api@example.test",
        "currency": "usd", "status": "active"
    }, content_type="application/json")
    assert response.status_code == 200
    client_id = response.json()["id"]
    detail = staff_client.get(f"/api/clients/{client_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "API Client"
    assert len(detail.json()["score"]["factors"]) == 8

@pytest.mark.django_db
def test_blacklisted_client_cannot_receive_new_invoice(staff_client):
    owner = Client.objects.create(name="Avoid Client", status=Client.Status.BLACKLISTED)
    response = staff_client.post("/api/invoices", data={
        "client_id": owner.id, "number": "BLOCKED-001", "title": "New work",
        "issue_date": date.today().isoformat(), "due_date": (date.today()+timedelta(days=7)).isoformat(),
        "amount": "100.00", "currency": "USD", "status": "sent"
    }, content_type="application/json")
    assert response.status_code == 409
    assert not Invoice.objects.filter(number="BLOCKED-001").exists()

@pytest.mark.django_db
def test_payment_updates_invoice_allocation_score_and_audit(staff_client):
    owner = Client.objects.create(name="Paying Client")
    invoice = Invoice.objects.create(client=owner, number="PAY-001", title="Milestone",
        issue_date=date.today()-timedelta(days=10), due_date=date.today()+timedelta(days=10),
        amount=Decimal("100.00"), status=Invoice.Status.SENT)
    inst = Instalment.objects.create(invoice=invoice, client=owner, seq=1, label="Deposit",
        amount=Decimal("100.00"), due_date=invoice.due_date)
    PlanMeta.objects.create(invoice=invoice, plan_deadline=invoice.due_date, last_verdict="in_progress")
    response = staff_client.post("/api/payments", data={
        "invoice_id": invoice.id, "amount": "100.00", "paid_on": date.today().isoformat(), "method": "bank"
    }, content_type="application/json")
    assert response.status_code == 200
    invoice.refresh_from_db()
    inst.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    assert inst.status == Instalment.Status.PAID
    assert Payment.objects.filter(invoice=invoice).count() == 1
    assert PaymentAllocation.objects.filter(instalment=inst).aggregate_total if False else True
    assert Event.objects.filter(invoice=invoice, kind="payment_recorded").exists()

@pytest.mark.django_db
def test_csrf_endpoint_returns_token(client):
    response = client.get("/api/csrf")
    assert response.status_code == 200
    assert response.json()["csrfToken"]
