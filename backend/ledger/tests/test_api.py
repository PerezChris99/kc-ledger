from datetime import date, timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.db.models import Sum
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
    assert PaymentAllocation.objects.filter(instalment=inst).aggregate(total=Sum('amount'))['total'] == Decimal('100.00')
    assert Event.objects.filter(invoice=invoice, kind="payment_recorded").exists()

@pytest.mark.django_db
def test_csrf_endpoint_returns_token(client):
    response = client.get("/api/csrf")
    assert response.status_code == 200
    assert response.json()["csrfToken"]


@pytest.mark.django_db
def test_plan_creation_requires_exact_outstanding_balance(staff_client):
    owner = Client.objects.create(name="Plan Client")
    invoice = Invoice.objects.create(client=owner, number="PLAN-001", title="Project",
        issue_date=date.today(), due_date=date.today()+timedelta(days=30),
        amount=Decimal("100.00"), status=Invoice.Status.SENT)
    response = staff_client.post("/api/plans", data={
        "invoice_id": invoice.id,
        "instalments": [
            {"seq": 1, "label": "First", "amount": "60.00", "due_date": (date.today()+timedelta(days=7)).isoformat(), "grace_days": 3},
            {"seq": 2, "label": "Final", "amount": "39.00", "due_date": (date.today()+timedelta(days=30)).isoformat(), "grace_days": 3}
        ]
    }, content_type="application/json")
    assert response.status_code == 422
    assert Instalment.objects.filter(invoice=invoice).count() == 0

@pytest.mark.django_db
def test_plan_creation_records_schedule_and_metadata(staff_client):
    owner = Client.objects.create(name="Plan Client Two")
    invoice = Invoice.objects.create(client=owner, number="PLAN-002", title="Project",
        issue_date=date.today(), due_date=date.today()+timedelta(days=30),
        amount=Decimal("100.00"), status=Invoice.Status.SENT)
    response = staff_client.post("/api/plans", data={
        "invoice_id": invoice.id,
        "instalments": [
            {"seq": 1, "label": "First", "amount": "60.00", "due_date": (date.today()+timedelta(days=7)).isoformat(), "grace_days": 3},
            {"seq": 2, "label": "Final", "amount": "40.00", "due_date": (date.today()+timedelta(days=30)).isoformat(), "grace_days": 3}
        ]
    }, content_type="application/json")
    assert response.status_code == 200
    assert Instalment.objects.filter(invoice=invoice).count() == 2
    assert PlanMeta.objects.filter(invoice=invoice).exists()
    assert Event.objects.filter(invoice=invoice, kind="instalment_plan_created").exists()


@pytest.mark.django_db
def test_plan_edit_preserves_old_rows_as_soft_deleted(staff_client):
    owner = Client.objects.create(name="Plan Edit Client")
    invoice = Invoice.objects.create(client=owner, number="PLAN-EDIT-001", title="Project",
        issue_date=date.today(), due_date=date.today()+timedelta(days=30),
        amount=Decimal("100.00"), status=Invoice.Status.SENT)
    first = [
        {"seq": 1, "label": "First", "amount": "60.00", "due_date": (date.today()+timedelta(days=7)).isoformat(), "grace_days": 3},
        {"seq": 2, "label": "Final", "amount": "40.00", "due_date": (date.today()+timedelta(days=30)).isoformat(), "grace_days": 3}
    ]
    created = staff_client.post("/api/plans", data={"invoice_id":invoice.id,"instalments":first}, content_type="application/json")
    assert created.status_code == 200
    second = [
        {"seq": 1, "label": "Phase A", "amount": "50.00", "due_date": (date.today()+timedelta(days=10)).isoformat(), "grace_days": 2},
        {"seq": 2, "label": "Phase B", "amount": "50.00", "due_date": (date.today()+timedelta(days=25)).isoformat(), "grace_days": 2}
    ]
    edited = staff_client.patch(f"/api/plans/{invoice.id}", data={"invoice_id":invoice.id,"instalments":second}, content_type="application/json")
    assert edited.status_code == 200
    assert Instalment.objects.filter(invoice=invoice).count() == 2
    assert Instalment.all_objects.filter(invoice=invoice, deleted_at__isnull=False).count() == 2
    assert Event.objects.filter(invoice=invoice, kind="instalment_plan_updated").exists()

@pytest.mark.django_db
def test_plan_edit_is_blocked_after_allocated_payment(staff_client):
    owner = Client.objects.create(name="Paid Plan Client")
    invoice = Invoice.objects.create(client=owner, number="PLAN-LOCK-001", title="Project",
        issue_date=date.today(), due_date=date.today()+timedelta(days=30),
        amount=Decimal("100.00"), status=Invoice.Status.SENT)
    inst = Instalment.objects.create(invoice=invoice, client=owner, seq=1, label="Deposit",
        amount=Decimal("100.00"), due_date=invoice.due_date)
    PlanMeta.objects.create(invoice=invoice, plan_deadline=invoice.due_date, last_verdict="in_progress")
    PaymentAllocation.objects.create(payment=Payment.objects.create(invoice=invoice, client=owner, amount=Decimal("1.00"), paid_on=date.today()), instalment=inst, amount=Decimal("1.00"))
    response = staff_client.patch(f"/api/plans/{invoice.id}", data={"invoice_id":invoice.id,"instalments":[
        {"seq":1,"label":"Revised","amount":"99.00","due_date":(date.today()+timedelta(days=14)).isoformat(),"grace_days":3}
    ]}, content_type="application/json")
    assert response.status_code == 409
    assert Instalment.objects.filter(pk=inst.pk).exists()


@pytest.mark.django_db
def test_worklog_records_engagement_time_and_expense(staff_client):
    owner = Client.objects.create(name="Worklog Client")
    engagement_response = staff_client.post("/api/engagements", data={
        "client_id": owner.id, "name": "Build sprint", "kind": "hourly",
        "agreed_amount": "500.00", "rate": "50.00", "currency": "USD",
        "start_date": date.today().isoformat(), "status": "active"
    }, content_type="application/json")
    assert engagement_response.status_code == 200
    engagement_id = engagement_response.json()["id"]
    time_response = staff_client.post("/api/time-entries", data={
        "engagement_id": engagement_id, "hours": "2.00", "category": "billable",
        "started_at": f"{date.today().isoformat()}T12:00:00", "note": "Implementation work"
    }, content_type="application/json")
    assert time_response.status_code == 200
    expense_response = staff_client.post("/api/expenses", data={
        "client_id": owner.id, "engagement_id": engagement_id, "category": "Hosting",
        "amount": "10.00", "currency": "USD", "spent_on": date.today().isoformat(),
        "billable": False, "note": "Test expense"
    }, content_type="application/json")
    assert expense_response.status_code == 200
    insights = staff_client.get("/api/insights")
    assert insights.status_code == 200
    rate = next(row for row in insights.json()["effective_rates"] if row["client"] == owner.name)
    assert Decimal(rate["hours"]) == Decimal("2.00")
    assert Decimal(rate["expenses"]) == Decimal("10.00")
    assert Decimal(rate["effective_hourly_rate"]) == Decimal("-5.00")
