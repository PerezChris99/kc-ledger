from datetime import date, datetime
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.middleware.csrf import get_token
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from ledger.models import Client, Engagement, Event, Expense, FxRate, Instalment, Invoice, Payment, PaymentAllocation, PlanMeta, TimeEntry
from ledger.services.instalments import allocate_payment_fifo, evaluate_plan_verdict
from ledger.services.scoring import compute_client_score

router = Router()

class LoginIn(Schema):
    username: str
    password: str

class ClientIn(Schema):
    name: str
    company: str = ""
    email: str = ""
    phone: str = ""
    country: str = ""
    currency: str = "USD"
    status: str = "active"
    notes: str = ""

class InvoiceIn(Schema):
    client_id: int
    engagement_id: int | None = None
    number: str
    title: str
    issue_date: date
    due_date: date
    amount: Decimal
    currency: str = "USD"
    status: str = "sent"
    notes: str = ""

class ClientPatch(Schema):
    name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    currency: str | None = None
    status: str | None = None
    notes: str | None = None

class InvoicePatch(Schema):
    title: str | None = None
    due_date: date | None = None
    status: str | None = None
    notes: str | None = None

class PaymentIn(Schema):
    invoice_id: int
    amount: Decimal
    paid_on: date
    method: str = ""
    reference: str = ""
    note: str = ""

class EngagementIn(Schema):
    client_id: int
    name: str
    kind: str = "fixed"
    agreed_amount: Decimal = Decimal("0")
    rate: Decimal | None = None
    currency: str = "USD"
    start_date: date | None = None
    end_date: date | None = None
    status: str = "active"
    scope_notes: str = ""
    revision_limit: int = 0
    revisions_used: int = 0
    recurring_interval_days: int = 0
    next_invoice_date: date | None = None

class EngagementPatch(Schema):
    name: str | None = None
    status: str | None = None
    agreed_amount: Decimal | None = None
    rate: Decimal | None = None
    currency: str | None = None
    end_date: date | None = None
    scope_notes: str | None = None
    revision_limit: int | None = None
    revisions_used: int | None = None
    recurring_interval_days: int | None = None
    next_invoice_date: date | None = None

class TimeEntryIn(Schema):
    engagement_id: int
    hours: Decimal
    category: str = "billable"
    started_at: datetime
    note: str = ""

class ExpenseIn(Schema):
    category: str
    amount: Decimal
    currency: str = "USD"
    spent_on: date
    client_id: int | None = None
    engagement_id: int | None = None
    billable: bool = False
    note: str = ""

def _client_snapshot(client):
    from ledger.api_extra import _get_app_settings
    base = _get_app_settings()["base_currency"]

    def convert(value, currency):
        currency = currency.upper()
        if currency == base:
            return value
        direct = FxRate.objects.filter(base=currency, quote=base).order_by("-fetched_at").first()
        if direct:
            return value * direct.rate
        inverse = FxRate.objects.filter(base=base, quote=currency).order_by("-fetched_at").first()
        if inverse and inverse.rate:
            return value / inverse.rate
        return None

    invoices = []
    currency_gaps = set()
    for invoice in client.invoices.annotate(paid_total=Sum("payments__amount")):
        collected_native = invoice.paid_total or Decimal("0")
        amount_base = convert(invoice.amount, invoice.currency)
        collected_base = convert(collected_native, invoice.currency)
        uncollected_native = max(Decimal("0"), invoice.amount-collected_native)
        writeoff_base = convert(uncollected_native, invoice.currency) if invoice.status == Invoice.Status.WRITTEN_OFF else Decimal("0")
        outstanding_base = Decimal("0") if invoice.status == Invoice.Status.WRITTEN_OFF else convert(uncollected_native, invoice.currency)
        if amount_base is None or collected_base is None or outstanding_base is None or writeoff_base is None:
            currency_gaps.add(invoice.currency)
            amount_base = collected_base = outstanding_base = writeoff_base = Decimal("0")
        invoices.append({"id": invoice.id, "number": invoice.number, "amount": amount_base,
            "outstanding": outstanding_base, "writeoff_amount": writeoff_base, "collected": collected_base, "due_date": invoice.due_date,
            "paid_on": invoice.paid_at.date() if invoice.paid_at else None, "status": invoice.status})

    events = list(client.events.filter(deleted_at__isnull=True))
    plans = []
    for invoice in client.invoices.all():
        rows = list(invoice.instalments.all())
        if rows:
            plans.append(evaluate_plan_verdict([{"due_date": r.due_date, "paid_on": r.paid_on,
                "status": r.status, "grace_days": r.grace_days, "amount": r.amount} for r in rows]))

    collected_by_client = {}
    for payment in Payment.objects.select_related("client", "invoice").all():
        value = convert(payment.amount, payment.invoice.currency)
        if value is None:
            if payment.client_id == client.id:
                currency_gaps.add(payment.invoice.currency)
            continue
        collected_by_client[payment.client_id] = collected_by_client.get(payment.client_id, Decimal("0")) + value
    lifetime_collected = collected_by_client.get(client.id, Decimal("0"))
    best_client_collected = max(collected_by_client.values(), default=Decimal("0"))
    expenses_total = Decimal("0")
    for expense in Expense.objects.filter(client=client):
        value = convert(expense.amount, expense.currency)
        if value is None:
            currency_gaps.add(expense.currency)
        else:
            expenses_total += value
    total_hours = TimeEntry.objects.filter(client=client).aggregate(total=Sum("hours"))["total"] or Decimal("0")
    outstanding_total = sum((row["outstanding"] for row in invoices), Decimal("0"))
    overdue_total = sum((row["outstanding"] for row in invoices if row["due_date"] < timezone.localdate()), Decimal("0"))
    net_contribution = lifetime_collected-expenses_total
    effective_hourly_rate = net_contribution/total_hours if total_hours > 0 else None

    return {"status": client.status, "invoices": invoices, "lifetime_collected": lifetime_collected,
        "best_client_collected": best_client_collected, "base_currency": base, "expenses_total": expenses_total,
        "net_contribution": net_contribution, "total_hours": total_hours, "effective_hourly_rate": effective_hourly_rate,
        "outstanding_total": outstanding_total, "overdue_total": overdue_total,
        "unconverted_currencies": sorted(currency_gaps),
        "engagement_count": client.engagements.count(), "started_at": client.started_at,
        "events": [{"kind": e.kind, "polarity": e.polarity, "weight": e.weight} for e in events],
        "plan_verdicts": plans, "chargebacks": sum(1 for e in events if e.kind == "chargeback"),
        "accepted_rate_increases": sum(1 for e in events if e.kind == "rate_increase_accepted"),
        "haggling_events": sum(1 for e in events if e.kind == "rate_haggling")}


def _refresh_score(client):
    result = compute_client_score(_client_snapshot(client))
    client.score = result.score
    client.score_updated_at = timezone.now()
    client.save(update_fields=["score", "score_updated_at", "updated_at"])
    return result

@router.get("/health", auth=None)
def health(request):
    return {"status": "ok", "service": "kc-ledger-api", "time": timezone.now().isoformat()}

@router.get("/csrf", auth=None)
def csrf_token(request):
    return {"csrfToken": get_token(request)}

@router.post("/auth/login", auth=None)
def auth_login(request, payload: LoginIn):
    from django.core.cache import cache
    from hashlib import sha256
    username = payload.username.strip()
    remote = request.META.get("REMOTE_ADDR", "unknown")
    throttle_key = "ledger-login:" + sha256(f"{remote}:{username.lower()}".encode()).hexdigest()
    if int(cache.get(throttle_key, 0)) >= 5:
        raise HttpError(429, "Too many sign-in attempts. Wait 15 minutes and try again.")
    user = authenticate(request, username=username, password=payload.password)
    if user is None or not user.is_active or not user.is_staff:
        if not cache.add(throttle_key, 1, timeout=900):
            try:
                cache.incr(throttle_key)
            except ValueError:
                cache.set(throttle_key, 1, timeout=900)
        raise HttpError(401, "Invalid credentials.")
    cache.delete(throttle_key)
    login(request, user)
    return {"authenticated": True, "username": user.get_username()}

@router.post("/auth/logout")
def auth_logout(request):
    logout(request)
    return {"authenticated": False}

@router.get("/session", auth=None)
def session_status(request):
    user = request.user
    return {"authenticated": bool(user.is_authenticated and user.is_staff),
        "username": user.get_username() if user.is_authenticated else None}

@router.get("/clients")
def list_clients(request, q: str = "", status: str = "", limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 100)
    qs = Client.objects.all().order_by("name")
    if q.strip():
        from django.db.models import Q
        qs = qs.filter(Q(name__icontains=q.strip()) | Q(company__icontains=q.strip()) | Q(email__icontains=q.strip()))
    if status:
        qs = qs.filter(status=status)
    total = qs.count()
    return {"items": [{"id": c.id, "name": c.name, "company": c.company, "email": c.email,
        "status": c.status, "score": c.score, "currency": c.currency, "updated_at": c.updated_at.isoformat()}
        for c in qs[offset:offset+limit]], "total": total, "limit": limit, "offset": max(0, offset)}

@router.post("/clients")
def create_client(request, payload: ClientIn):
    if payload.status not in Client.Status.values:
        raise HttpError(422, "Unsupported client status.")
    values = payload.dict()
    values["currency"] = values["currency"].upper()
    if len(values["currency"]) != 3:
        raise HttpError(422, "Currency must be a three-letter code.")
    client = Client.objects.create(**values)
    Event.objects.create(client=client, kind="client_created", category=Event.Category.RELATIONSHIP,
        polarity=0, title="Client created", detail="Client record created.", occurred_at=timezone.now())
    result = _refresh_score(client)
    return {"id": client.id, "name": client.name, "score": result.score}

@router.get("/clients/{client_id}")
def client_detail(request, client_id: int):
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        raise HttpError(404, "Client not found.")
    snapshot = _client_snapshot(client)
    score = compute_client_score(snapshot).as_dict()
    invoices = []
    for inv in client.invoices.select_related("engagement").annotate(paid_total=Sum("payments__amount")):
        paid = inv.paid_total or Decimal("0")
        invoices.append({"id": inv.id, "number": inv.number, "title": inv.title, "issue_date": inv.issue_date.isoformat(),
            "due_date": inv.due_date.isoformat(), "amount": str(inv.amount), "collected": str(paid),
            "outstanding": str(Decimal("0") if inv.status == Invoice.Status.WRITTEN_OFF else max(Decimal("0"), inv.amount-paid)), "currency": inv.currency, "status": inv.status,
            "engagement": inv.engagement.name if inv.engagement else None})
    payments = [{"id": p.id, "invoice_number": p.invoice.number, "amount": str(p.amount),
        "currency": p.invoice.currency, "paid_on": p.paid_on.isoformat(), "method": p.method, "reference": p.reference}
        for p in client.payments.select_related("invoice").all()[:100]]
    events = [{"id": e.id, "kind": e.kind, "category": e.category, "polarity": e.polarity, "title": e.title,
        "detail": e.detail, "occurred_at": e.occurred_at.isoformat()} for e in client.events.filter(deleted_at__isnull=True)[:200]]
    return {"id": client.id, "name": client.name, "company": client.company, "email": client.email, "phone": client.phone,
        "country": client.country, "currency": client.currency, "status": client.status, "notes": client.notes,
        "score": score, "score_currency": snapshot["base_currency"], "financials": {
            "currency": snapshot["base_currency"], "collected": str(snapshot["lifetime_collected"]),
            "outstanding": str(snapshot["outstanding_total"]), "overdue": str(snapshot["overdue_total"]),
            "expenses": str(snapshot["expenses_total"]), "net_contribution": str(snapshot["net_contribution"]),
            "hours": str(snapshot["total_hours"]), "effective_hourly_rate": str(snapshot["effective_hourly_rate"]) if snapshot["effective_hourly_rate"] is not None else None,
            "unconverted_currencies": snapshot["unconverted_currencies"]},
        "invoices": invoices, "payments": payments, "events": events,
        "engagements": [{"id": e.id, "name": e.name, "kind": e.kind, "status": e.status,
            "amount": str(e.agreed_amount), "currency": e.currency} for e in client.engagements.all()]}

@router.patch("/clients/{client_id}")
def update_client(request, client_id: int, payload: ClientPatch):
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        raise HttpError(404, "Client not found.")
    changes = {key: value for key, value in payload.dict(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HttpError(422, "Provide at least one field to update.")
    if "status" in changes and changes["status"] not in Client.Status.values:
        raise HttpError(422, "Unsupported client status.")
    if "currency" in changes:
        changes["currency"] = changes["currency"].upper()
        if len(changes["currency"]) != 3:
            raise HttpError(422, "Currency must be a three-letter code.")
    for key, value in changes.items():
        setattr(client, key, value)
    client.save()
    Event.objects.create(client=client, kind="client_updated", category=Event.Category.RELATIONSHIP,
        polarity=0, title="Client record updated", detail=f"Updated fields: {', '.join(sorted(changes))}.",
        occurred_at=timezone.now())
    score = _refresh_score(client)
    return {"id": client.id, "name": client.name, "status": client.status, "score": score.score}

@router.delete("/clients/{client_id}")
def archive_client(request, client_id: int):
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        raise HttpError(404, "Client not found.")
    Event.objects.create(client=client, kind="client_archived", category=Event.Category.RELATIONSHIP,
        polarity=0, title="Client archived", detail="Client record was soft-deleted; related financial history is retained.",
        occurred_at=timezone.now())
    client.status = Client.Status.ARCHIVED
    client.save(update_fields=["status", "updated_at"])
    client.soft_delete()
    return {"id": client.id, "archived": True}

@router.get("/invoices")
def list_invoices(request, status: str = "", q: str = "", limit: int = 50, offset: int = 0):
    from django.db.models import Q
    limit = min(max(limit, 1), 100)
    qs = Invoice.objects.select_related("client").annotate(paid_total=Sum("payments__amount"))
    if status:
        qs = qs.filter(status=status)
    if q.strip():
        qs = qs.filter(Q(number__icontains=q.strip()) | Q(title__icontains=q.strip()) | Q(client__name__icontains=q.strip()))
    total = qs.count()
    items = []
    for inv in qs.order_by("-issue_date", "-id")[offset:offset+limit]:
        paid = inv.paid_total or Decimal("0")
        items.append({"id": inv.id, "number": inv.number, "title": inv.title, "client_id": inv.client_id,
            "client_name": inv.client.name, "amount": str(inv.amount), "collected": str(paid),
            "outstanding": str(Decimal("0") if inv.status == Invoice.Status.WRITTEN_OFF else max(Decimal("0"), inv.amount-paid)), "currency": inv.currency,
            "issue_date": inv.issue_date.isoformat(), "due_date": inv.due_date.isoformat(), "status": inv.status, "notes": inv.notes})
    return {"items": items, "total": total, "limit": limit, "offset": max(0, offset)}

@router.post("/invoices")
def create_invoice(request, payload: InvoiceIn):
    if payload.amount <= 0:
        raise HttpError(422, "Invoice amount must be positive.")
    if payload.due_date < payload.issue_date:
        raise HttpError(422, "Invoice due date cannot precede issue date.")
    if payload.status not in {Invoice.Status.DRAFT, Invoice.Status.SENT, Invoice.Status.DISPUTED}:
        raise HttpError(422, "New invoices must be draft, sent, or disputed.")
    if len(payload.currency) != 3:
        raise HttpError(422, "Currency must be a three-letter code.")
    try:
        client = Client.objects.get(pk=payload.client_id)
    except Client.DoesNotExist:
        raise HttpError(404, "Client not found.")
    client_score = compute_client_score(_client_snapshot(client))
    if client.status == Client.Status.BLACKLISTED or client_score.score < 40:
        raise HttpError(409, f"Invoice creation blocked: {client.name} is classified {client_score.tier} (score {client_score.score}). Review the client dossier before taking on new work.")
    engagement = None
    if payload.engagement_id:
        try:
            engagement = Engagement.objects.get(pk=payload.engagement_id, client=client)
        except Engagement.DoesNotExist:
            raise HttpError(422, "Engagement does not belong to this client.")
    invoice_values = payload.dict(exclude={"client_id", "engagement_id"})
    invoice_values["currency"] = payload.currency.upper()
    try:
        inv = Invoice.objects.create(client=client, engagement=engagement, **invoice_values)
    except IntegrityError:
        raise HttpError(409, "An invoice with that number already exists.")
    Event.objects.create(client=client, engagement=engagement, invoice=inv, kind="invoice_created",
        category=Event.Category.MONEY, polarity=0, title=f"Invoice {inv.number} created",
        detail=f"Invoice amount {inv.amount} {inv.currency}.", amount=inv.amount, occurred_at=timezone.now())
    _refresh_score(client)
    return {"id": inv.id, "number": inv.number, "status": inv.status}

@router.patch("/invoices/{invoice_id}")
def update_invoice(request, invoice_id: int, payload: InvoicePatch):
    try:
        invoice = Invoice.objects.select_related("client").get(pk=invoice_id)
    except Invoice.DoesNotExist:
        raise HttpError(404, "Invoice not found.")
    changes = {key: value for key, value in payload.dict(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HttpError(422, "Provide at least one field to update.")
    if "due_date" in changes and changes["due_date"] < invoice.issue_date:
        raise HttpError(422, "Invoice due date cannot precede issue date.")
    allowed = {Invoice.Status.DRAFT, Invoice.Status.SENT, Invoice.Status.DISPUTED, Invoice.Status.WRITTEN_OFF}
    if "status" in changes:
        if changes["status"] not in allowed:
            raise HttpError(422, "Paid and partial statuses are managed by the payment workflow.")
        if changes["status"] == Invoice.Status.WRITTEN_OFF and invoice.status != Invoice.Status.WRITTEN_OFF:
            Event.objects.create(client=invoice.client, engagement=invoice.engagement, invoice=invoice,
                kind="invoice_written_off", category=Event.Category.MONEY, polarity=-1,
                title=f"Invoice {invoice.number} written off", detail=f"Written-off amount {invoice.amount} {invoice.currency}.",
                amount=invoice.amount, occurred_at=timezone.now())
    for key, value in changes.items():
        setattr(invoice, key, value)
    invoice.save()
    Event.objects.create(client=invoice.client, engagement=invoice.engagement, invoice=invoice,
        kind="invoice_updated", category=Event.Category.MONEY, polarity=0, title=f"Invoice {invoice.number} updated",
        detail=f"Updated fields: {', '.join(sorted(changes))}.", occurred_at=timezone.now())
    score = _refresh_score(invoice.client)
    return {"id": invoice.id, "number": invoice.number, "status": invoice.status, "score": score.score}

@router.post("/payments")
def record_payment(request, payload: PaymentIn):
    if payload.amount <= 0:
        raise HttpError(422, "Payment amount must be positive.")
    if payload.paid_on > timezone.localdate():
        raise HttpError(422, "Payment date cannot be in the future.")
    with transaction.atomic():
        try:
            inv = Invoice.objects.select_for_update().select_related("client").get(pk=payload.invoice_id)
        except Invoice.DoesNotExist:
            raise HttpError(404, "Invoice not found.")
        if inv.status == Invoice.Status.WRITTEN_OFF:
            raise HttpError(422, "Written-off invoices cannot receive payments.")
        prior = inv.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        if payload.amount > inv.amount-prior:
            raise HttpError(422, "Payment exceeds the outstanding invoice balance.")
        payment = Payment.objects.create(invoice=inv, client=inv.client, amount=payload.amount,
            paid_on=payload.paid_on, method=payload.method, reference=payload.reference, note=payload.note)
        rows = list(inv.instalments.all())
        prior_verdict = evaluate_plan_verdict([{"due_date": r.due_date, "paid_on": r.paid_on, "status": r.status,
            "grace_days": r.grace_days, "amount": r.amount} for r in rows]) if rows else None
        allocation = {"allocations": [], "unallocated": payload.amount}
        if rows:
            existing = PaymentAllocation.objects.filter(instalment__in=rows).values("instalment_id").annotate(total=Sum("amount"))
            paid_map = {x["instalment_id"]: x["total"] for x in existing}
            allocation = allocate_payment_fifo([{"id": r.id, "seq": r.seq, "due_date": r.due_date,
                "amount": r.amount, "allocated": paid_map.get(r.id, Decimal("0")), "status": r.status} for r in rows], payload.amount)
            for item in allocation["allocations"]:
                PaymentAllocation.objects.create(payment=payment, instalment_id=item["instalment_id"], amount=item["amount"])
            for row in rows:
                total = PaymentAllocation.objects.filter(instalment=row).aggregate(total=Sum("amount"))["total"] or Decimal("0")
                if total >= row.amount:
                    row.status, row.paid_on = Instalment.Status.PAID, payload.paid_on
                elif total > 0:
                    row.status = Instalment.Status.LATE if payload.paid_on > row.due_date else Instalment.Status.PENDING
                row.save(update_fields=["status", "paid_on", "updated_at"])
        prior += payload.amount
        was_disputed = inv.status == Invoice.Status.DISPUTED
        inv.status = Invoice.Status.DISPUTED if was_disputed else Invoice.Status.PAID if prior >= inv.amount else Invoice.Status.PARTIAL
        if prior >= inv.amount:
            inv.paid_at = timezone.now()
        inv.save(update_fields=["status", "paid_at", "updated_at"])
        Event.objects.create(client=inv.client, engagement=inv.engagement, invoice=inv, payment=payment,
            kind="payment_recorded", category=Event.Category.MONEY, polarity=1, title=f"Payment recorded for {inv.number}",
            detail=f"Recorded {payload.amount} {inv.currency}.", amount=payload.amount, occurred_at=timezone.now())
        if rows:
            current_rows = list(inv.instalments.all())
            new_verdict = evaluate_plan_verdict([{"due_date": r.due_date, "paid_on": r.paid_on, "status": r.status,
                "grace_days": r.grace_days, "amount": r.amount} for r in current_rows])
            if prior_verdict != new_verdict:
                plan_meta = PlanMeta.objects.filter(invoice=inv).first()
                if plan_meta:
                    plan_meta.last_verdict = new_verdict
                    plan_meta.save(update_fields=["last_verdict", "updated_at"])
                polarity = 1 if new_verdict == "perfect" else -1 if new_verdict in {"late", "at_risk", "broken"} else 0
                Event.objects.create(client=inv.client, engagement=inv.engagement, invoice=inv,
                    kind=f"plan_verdict_{new_verdict}", category=Event.Category.MONEY, polarity=polarity,
                    title=f"Plan verdict changed: {new_verdict.replace('_', ' ')}",
                    detail=f"{inv.number}: {prior_verdict.replace('_', ' ')} → {new_verdict.replace('_', ' ')}.",
                    occurred_at=timezone.now())
        score = _refresh_score(inv.client)
    return {"payment_id": payment.id, "invoice_status": inv.status, "score": score.score,
        "allocation": [{"instalment_id": a["instalment_id"], "amount": str(a["amount"])} for a in allocation["allocations"]],
        "unallocated": str(allocation["unallocated"])}

@router.get("/plans")
def list_plans(request):
    items = []
    for inv in Invoice.objects.select_related("client").prefetch_related("instalments").all():
        rows = list(inv.instalments.all())
        if not rows:
            continue
        verdict = evaluate_plan_verdict([{"due_date": r.due_date, "paid_on": r.paid_on, "status": r.status,
            "grace_days": r.grace_days, "amount": r.amount} for r in rows])
        items.append({"invoice_id": inv.id, "invoice_number": inv.number, "client_id": inv.client_id,
            "client_name": inv.client.name, "verdict": verdict, "instalments": [{"id": r.id, "seq": r.seq,
            "label": r.label, "amount": str(r.amount), "due_date": r.due_date.isoformat(), "grace_days": r.grace_days, "status": r.status,
            "paid_on": r.paid_on.isoformat() if r.paid_on else None} for r in rows]})
    return {"items": items}

@router.get("/engagements")
def list_engagements(request, client_id: int | None = None, status: str = "", limit: int = 100):
    limit = min(max(limit, 1), 200)
    qs = Engagement.objects.select_related("client").order_by("-created_at")
    if client_id is not None:
        qs = qs.filter(client_id=client_id)
    if status:
        qs = qs.filter(status=status)
    return {"items": [{"id": e.id, "client_id": e.client_id, "client_name": e.client.name, "name": e.name,
        "kind": e.kind, "agreed_amount": str(e.agreed_amount), "rate": str(e.rate) if e.rate is not None else None,
        "currency": e.currency, "start_date": e.start_date.isoformat() if e.start_date else None,
        "end_date": e.end_date.isoformat() if e.end_date else None, "status": e.status, "scope_notes": e.scope_notes,
        "revision_limit": e.revision_limit, "revisions_used": e.revisions_used,
        "recurring_interval_days": e.recurring_interval_days,
        "next_invoice_date": e.next_invoice_date.isoformat() if e.next_invoice_date else None}
        for e in qs[:limit]]}

@router.post("/engagements")
def create_engagement(request, payload: EngagementIn):
    if payload.kind not in Engagement.Kind.values or payload.status not in Engagement.Status.values:
        raise HttpError(422, "Unsupported engagement kind or status.")
    if payload.agreed_amount < 0 or (payload.rate is not None and payload.rate < 0):
        raise HttpError(422, "Engagement amounts and rates cannot be negative.")
    if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
        raise HttpError(422, "Engagement end date cannot precede its start date.")
    if payload.recurring_interval_days < 0 or payload.recurring_interval_days > 365:
        raise HttpError(422, "Recurring interval must be between 0 and 365 days.")
    if payload.recurring_interval_days and (payload.kind != Engagement.Kind.RETAINER or not payload.next_invoice_date):
        raise HttpError(422, "Recurring invoices require a retainer engagement and a next invoice date.")
    try:
        client = Client.objects.get(pk=payload.client_id)
    except Client.DoesNotExist:
        raise HttpError(404, "Client not found.")
    values = payload.dict(exclude={"client_id"})
    values["currency"] = values["currency"].upper()
    if len(values["currency"]) != 3 or not values["currency"].isalpha():
        raise HttpError(422, "Currency must be a three-letter code.")
    engagement = Engagement.objects.create(client=client, **values)
    Event.objects.create(client=client, engagement=engagement, kind="engagement_created", category=Event.Category.DELIVERY,
        polarity=0, title=f"Engagement created: {engagement.name}", detail=f"Type: {engagement.kind}.",
        occurred_at=timezone.now())
    _refresh_score(client)
    return {"id": engagement.id, "name": engagement.name, "status": engagement.status}

@router.patch("/engagements/{engagement_id}")
def update_engagement(request, engagement_id: int, payload: EngagementPatch):
    try:
        engagement = Engagement.objects.select_related("client").get(pk=engagement_id)
    except Engagement.DoesNotExist:
        raise HttpError(404, "Engagement not found.")
    changes = {key: value for key, value in payload.dict(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HttpError(422, "Provide at least one field to update.")
    if "status" in changes and changes["status"] not in Engagement.Status.values:
        raise HttpError(422, "Unsupported engagement status.")
    if "agreed_amount" in changes and changes["agreed_amount"] < 0:
        raise HttpError(422, "Agreed amount cannot be negative.")
    if "rate" in changes and changes["rate"] is not None and changes["rate"] < 0:
        raise HttpError(422, "Rate cannot be negative.")
    if "currency" in changes:
        changes["currency"] = changes["currency"].upper()
        if len(changes["currency"]) != 3 or not changes["currency"].isalpha():
            raise HttpError(422, "Currency must be a three-letter code.")
    next_kind = changes.get("kind", engagement.kind)
    next_interval = changes.get("recurring_interval_days", engagement.recurring_interval_days)
    next_date = changes.get("next_invoice_date", engagement.next_invoice_date)
    if next_interval and (next_kind != Engagement.Kind.RETAINER or not next_date):
        raise HttpError(422, "Recurring invoices require a retainer engagement and a next invoice date.")
    for key, value in changes.items():
        setattr(engagement, key, value)
    engagement.save()
    Event.objects.create(client=engagement.client, engagement=engagement, kind="engagement_updated",
        category=Event.Category.DELIVERY, polarity=0, title=f"Engagement updated: {engagement.name}",
        detail=f"Updated fields: {', '.join(sorted(changes))}.", occurred_at=timezone.now())
    return {"id": engagement.id, "name": engagement.name, "status": engagement.status}

@router.get("/time-entries")
def list_time_entries(request, client_id: int | None = None, limit: int = 100):
    limit = min(max(limit, 1), 200)
    qs = TimeEntry.objects.select_related("client", "engagement").order_by("-started_at")
    if client_id is not None:
        qs = qs.filter(client_id=client_id)
    return {"items": [{"id": row.id, "client_id": row.client_id, "client_name": row.client.name,
        "engagement_id": row.engagement_id, "engagement_name": row.engagement.name, "hours": str(row.hours),
        "category": row.category, "started_at": row.started_at.isoformat(), "note": row.note}
        for row in qs[:limit]]}

@router.post("/time-entries")
def create_time_entry(request, payload: TimeEntryIn):
    if payload.hours <= 0:
        raise HttpError(422, "Hours must be positive.")
    if payload.category not in TimeEntry.Category.values:
        raise HttpError(422, "Unsupported time-entry category.")
    try:
        engagement = Engagement.objects.select_related("client").get(pk=payload.engagement_id)
    except Engagement.DoesNotExist:
        raise HttpError(404, "Engagement not found.")
    started_at = payload.started_at
    if timezone.is_naive(started_at):
        started_at = timezone.make_aware(started_at, timezone.get_current_timezone())
    entry = TimeEntry.objects.create(client=engagement.client, engagement=engagement, hours=payload.hours,
        category=payload.category, started_at=started_at, note=payload.note)
    Event.objects.create(client=engagement.client, engagement=engagement, kind="time_entry_recorded",
        category=Event.Category.DELIVERY, polarity=0, title=f"Time recorded: {engagement.name}",
        detail=f"{entry.hours} hours · {entry.category}. {entry.note}".strip(), occurred_at=timezone.now())
    return {"id": entry.id, "hours": str(entry.hours), "client_id": entry.client_id}

@router.get("/expenses")
def list_expenses(request, client_id: int | None = None, limit: int = 100):
    limit = min(max(limit, 1), 200)
    qs = Expense.objects.select_related("client", "engagement").order_by("-spent_on")
    if client_id is not None:
        qs = qs.filter(client_id=client_id)
    return {"items": [{"id": row.id, "client_id": row.client_id, "client_name": row.client.name if row.client else None,
        "engagement_id": row.engagement_id, "engagement_name": row.engagement.name if row.engagement else None,
        "category": row.category, "amount": str(row.amount), "currency": row.currency, "spent_on": row.spent_on.isoformat(),
        "billable": row.billable, "note": row.note} for row in qs[:limit]]}

@router.post("/expenses")
def create_expense(request, payload: ExpenseIn):
    if payload.amount <= 0:
        raise HttpError(422, "Expense amount must be positive.")
    if not payload.category.strip():
        raise HttpError(422, "Expense category is required.")
    client = None
    engagement = None
    if payload.client_id is not None:
        client = Client.objects.filter(pk=payload.client_id).first()
        if client is None:
            raise HttpError(404, "Client not found.")
    if payload.engagement_id is not None:
        engagement = Engagement.objects.select_related("client").filter(pk=payload.engagement_id).first()
        if engagement is None:
            raise HttpError(404, "Engagement not found.")
        if client is not None and engagement.client_id != client.id:
            raise HttpError(422, "Engagement does not belong to the selected client.")
        client = client or engagement.client
    currency = payload.currency.upper()
    if len(currency) != 3 or not currency.isalpha():
        raise HttpError(422, "Currency must be a three-letter code.")
    expense = Expense.objects.create(client=client, engagement=engagement, category=payload.category.strip()[:80],
        amount=payload.amount, currency=currency, spent_on=payload.spent_on, billable=payload.billable, note=payload.note)
    Event.objects.create(client=client, engagement=engagement, kind="expense_recorded", category=Event.Category.MONEY,
        polarity=0, title=f"Expense recorded: {expense.category}", detail=f"{expense.amount} {expense.currency} spent on {expense.spent_on}.",
        amount=expense.amount, occurred_at=timezone.now())
    return {"id": expense.id, "amount": str(expense.amount), "currency": expense.currency}

@router.get("/dashboard")
def dashboard(request):
    from ledger.api_extra import _get_app_settings
    base = _get_app_settings()["base_currency"]
    today = timezone.localdate()
    def convert(value, currency):
        currency = currency.upper()
        if currency == base:
            return value
        rate = FxRate.objects.filter(base=currency, quote=base).order_by("-fetched_at").first()
        if rate:
            return value * rate.rate
        inverse = FxRate.objects.filter(base=base, quote=currency).order_by("-fetched_at").first()
        return value / inverse.rate if inverse and inverse.rate else None
    collected = outstanding = overdue = expenses_total = Decimal("0")
    unknown = set()
    invoices = list(Invoice.objects.select_related("client").annotate(paid_total=Sum("payments__amount")))
    for inv in invoices:
        paid = inv.paid_total or Decimal("0")
        paid_base = convert(paid, inv.currency)
        balance_base = Decimal("0") if inv.status == Invoice.Status.WRITTEN_OFF else convert(max(Decimal("0"), inv.amount-paid), inv.currency)
        if paid_base is None or balance_base is None:
            unknown.add(inv.currency)
            continue
        collected += paid_base
        outstanding += balance_base
        if inv.due_date < today and inv.status not in {Invoice.Status.PAID, Invoice.Status.WRITTEN_OFF}:
            overdue += balance_base
    for expense in Expense.objects.all():
        amount = convert(expense.amount, expense.currency)
        if amount is None:
            unknown.add(expense.currency)
        else:
            expenses_total += amount
    attention = [{"kind": "overdue_invoice", "title": f"{i.number} overdue", "client": i.client.name,
        "due_date": i.due_date.isoformat()} for i in invoices if i.due_date < today and i.status not in {Invoice.Status.PAID, Invoice.Status.WRITTEN_OFF}]
    from datetime import timedelta
    month_starts = []
    cursor = today.replace(day=1)
    for _ in range(5):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    for _ in range(6):
        month_starts.append(cursor)
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    revenue_by_month = {m.strftime("%Y-%m"): Decimal("0") for m in month_starts}
    expense_by_month = {m.strftime("%Y-%m"): Decimal("0") for m in month_starts}
    for payment in Payment.objects.select_related("invoice").all():
        key = payment.paid_on.strftime("%Y-%m")
        if key in revenue_by_month:
            value = convert(payment.amount, payment.invoice.currency)
            if value is None:
                unknown.add(payment.invoice.currency)
            else:
                revenue_by_month[key] += value
    for expense in Expense.objects.all():
        key = expense.spent_on.strftime("%Y-%m")
        if key in expense_by_month:
            value = convert(expense.amount, expense.currency)
            if value is None:
                unknown.add(expense.currency)
            else:
                expense_by_month[key] += value
    revenue_trend = [{"month": key, "revenue": float(revenue_by_month[key]), "expenses": float(expense_by_month[key])} for key in revenue_by_month]
    invoice_status = [{"status": status, "count": sum(1 for item in invoices if item.status == status)} for status, _ in Invoice.Status.choices]
    aging_totals = {"not_due": Decimal("0"), "1_30": Decimal("0"), "31_60": Decimal("0"), "61_plus": Decimal("0")}
    client_revenue = {}
    for inv in invoices:
        paid = inv.paid_total or Decimal("0")
        balance = Decimal("0") if inv.status == Invoice.Status.WRITTEN_OFF else max(Decimal("0"), inv.amount-paid)
        value = convert(balance, inv.currency)
        if value is not None:
            age = (today-inv.due_date).days
            bucket = "not_due" if age <= 0 else "1_30" if age <= 30 else "31_60" if age <= 60 else "61_plus"
            aging_totals[bucket] += value
    for payment in Payment.objects.select_related("client", "invoice").all():
        value = convert(payment.amount, payment.invoice.currency)
        if value is not None:
            client_revenue[payment.client_id] = client_revenue.get(payment.client_id, {"name": payment.client.name, "amount": Decimal("0")})
            client_revenue[payment.client_id]["amount"] += value
    concentration_total = sum((row["amount"] for row in client_revenue.values()), Decimal("0"))
    concentration = sorted(client_revenue.values(), key=lambda row: row["amount"], reverse=True)[:5]
    for row in concentration:
        row["collected"] = str(row.pop("amount"))
        row["share"] = float(Decimal(row["collected"])/concentration_total) if concentration_total else 0
    health_rows = [{"id": client.id, "name": client.name, "status": client.status, "score": client.score,
        "company": client.company} for client in Client.objects.order_by("-score", "name")[:8]]
    today_items = []
    for inst in Instalment.objects.select_related("invoice", "client").filter(due_date__range=(today, today+timedelta(days=3))).exclude(status__in=[Instalment.Status.PAID, Instalment.Status.WAIVED])[:10]:
        today_items.append({"kind": "instalment_due", "title": f"{inst.invoice.number} · {inst.label} due", "client": inst.client.name, "due_date": inst.due_date.isoformat()})
    return {"currency": base, "collected": str(collected), "outstanding": str(outstanding), "overdue": str(overdue),
        "expenses": str(expenses_total), "net_profit": str(collected-expenses_total), "client_count": Client.objects.count(),
        "invoice_count": len(invoices), "payment_count": Payment.objects.count(), "total_hours": str(TimeEntry.objects.aggregate(total=Sum("hours"))["total"] or Decimal("0")), "attention": attention[:10], "today": today_items[:5],
        "revenue_trend": revenue_trend, "invoice_status": invoice_status,
        "aging": [{"bucket": key, "amount": str(value)} for key,value in aging_totals.items()],
        "client_health": health_rows, "concentration": concentration,
        "unconverted_currencies": sorted(unknown)}
