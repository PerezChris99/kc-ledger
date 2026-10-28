from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from ledger.models import Client, Event, Expense, FxRate, Instalment, Invoice, Meta, Payment, PaymentAllocation, PlanMeta, Target, TimeEntry

router = Router()

def _recompute_client_scores():
    from ledger.api import _refresh_score
    for client in Client.objects.all():
        _refresh_score(client)

class SettingsIn(Schema):
    base_currency: str | None = None
    time_zone: str | None = None
    notifications_enabled: bool | None = None
    sounds: dict[str, bool] | None = None

class TargetIn(Schema):
    name: str
    type: str
    amount: Decimal
    currency: str = "USD"
    deadline: date

class FxRateIn(Schema):
    base: str
    quote: str
    rate: Decimal
    source: str = "manual"

@router.get("/events")
def list_events(request, category: str = "", q: str = "", limit: int = 100, offset: int = 0):
    limit = min(max(limit, 1), 200)
    qs = Event.objects.filter(deleted_at__isnull=True).select_related("client").order_by("-occurred_at", "-id")
    if category:
        qs = qs.filter(category=category)
    if q.strip():
        from django.db.models import Q
        qs = qs.filter(Q(title__icontains=q.strip()) | Q(detail__icontains=q.strip()) | Q(client__name__icontains=q.strip()))
    total = qs.count()
    return {"items": [{"id": e.id, "title": e.title, "detail": e.detail, "kind": e.kind, "category": e.category,
        "polarity": e.polarity, "amount": str(e.amount) if e.amount is not None else None,
        "client": e.client.name if e.client else None, "occurred_at": e.occurred_at.isoformat()}
        for e in qs[offset:offset+limit]], "total": total}

@router.get("/insights")
def insights(request):
    base = _get_app_settings()["base_currency"]
    today = timezone.localdate()
    buckets = {"not_due": Decimal("0"), "1_30": Decimal("0"), "31_60": Decimal("0"), "61_plus": Decimal("0")}
    currency_gaps = set()
    concentration = {}
    for invoice in Invoice.objects.select_related("client").annotate(paid_total=Sum("payments__amount")):
        paid = invoice.paid_total or Decimal("0")
        balance = max(Decimal("0"), invoice.amount-paid)
        if balance <= 0:
            continue
        rate = Decimal("1") if invoice.currency == base else None
        if rate is None:
            fx = FxRate.objects.filter(base=invoice.currency, quote=base).order_by("-fetched_at").first()
            inv = FxRate.objects.filter(base=base, quote=invoice.currency).order_by("-fetched_at").first()
            if fx: rate = fx.rate
            elif inv and inv.rate: rate = Decimal("1")/inv.rate
        if rate is None:
            currency_gaps.add(invoice.currency)
            continue
        balance *= rate
        age = (today-invoice.due_date).days
        key = "not_due" if age <= 0 else "1_30" if age <= 30 else "31_60" if age <= 60 else "61_plus"
        buckets[key] += balance
    for payment in Payment.objects.select_related("client", "invoice").all():
        if payment.invoice.currency != base:
            fx = FxRate.objects.filter(base=payment.invoice.currency, quote=base).order_by("-fetched_at").first()
            inv = FxRate.objects.filter(base=base, quote=payment.invoice.currency).order_by("-fetched_at").first()
            if fx: value = payment.amount*fx.rate
            elif inv and inv.rate: value = payment.amount/inv.rate
            else:
                currency_gaps.add(payment.invoice.currency)
                continue
        else: value = payment.amount
        concentration[payment.client.name] = concentration.get(payment.client.name, Decimal("0")) + value
    total_collected = sum(concentration.values(), Decimal("0"))
    top = sorted(concentration.items(), key=lambda x: x[1], reverse=True)[:10]
    return {"currency": base, "aging": [{"bucket": k, "amount": str(v)} for k, v in buckets.items()],
        "concentration": [{"client": k, "collected": str(v), "share": float(v/total_collected) if total_collected else 0} for k,v in top],
        "time_entries": TimeEntry.objects.count(), "expenses_count": Expense.objects.count(),
        "unconverted_currencies": sorted(currency_gaps)}

def _target_progress(target):
    today = timezone.localdate()
    current = Decimal("0")
    conversion_available = True
    if target.type == Target.Type.REVENUE:
        for payment in Payment.objects.select_related("invoice").all():
            value = payment.amount
            currency = payment.invoice.currency.upper()
            if currency != target.currency.upper():
                direct = FxRate.objects.filter(base=currency, quote=target.currency.upper()).order_by("-fetched_at").first()
                inverse = FxRate.objects.filter(base=target.currency.upper(), quote=currency).order_by("-fetched_at").first()
                if direct:
                    value *= direct.rate
                elif inverse and inverse.rate:
                    value /= inverse.rate
                else:
                    conversion_available = False
                    continue
            current += value
    elif target.type == Target.Type.CLIENTS:
        current = Decimal(Client.objects.filter(status=Client.Status.ACTIVE).count())
    else:
        current = TimeEntry.objects.aggregate(total=Sum("hours"))["total"] or Decimal("0")
    progress = min(100.0, float(current/target.amount*100)) if target.amount else 0.0
    duration = max(1, (target.deadline-target.created_at.date()).days)
    elapsed = max(0, (today-target.created_at.date()).days)
    expected = target.amount * Decimal(min(1.0, elapsed/duration))
    days_remaining = (target.deadline-today).days
    if target.type == Target.Type.REVENUE and not conversion_available:
        pace = "fx_missing"
    else:
        pace = "on_track" if current >= expected else "behind"
    return {"current": str(current), "progress_pct": progress, "pace_status": pace,
        "days_remaining": days_remaining, "conversion_available": conversion_available}

@router.get("/targets")
def list_targets(request):
    items = []
    for target in Target.objects.order_by("deadline"):
        items.append({"id": target.id, "name": target.name, "type": target.type, "amount": str(target.amount),
            "currency": target.currency, "deadline": target.deadline.isoformat(), "created_at": target.created_at.isoformat(),
            **_target_progress(target)})
    return {"items": items}

@router.post("/targets")
def create_target(request, payload: TargetIn):
    if payload.amount <= 0:
        raise HttpError(422, "Target amount must be positive.")
    if payload.type not in {"revenue", "clients", "hours"}:
        raise HttpError(422, "Unsupported target type.")
    values = payload.dict()
    values["currency"] = values["currency"].upper()
    if len(values["currency"]) != 3 or not values["currency"].isalpha():
        raise HttpError(422, "Currency must be a three-letter code.")
    target = Target.objects.create(**values)
    Event.objects.create(kind="target_created", category=Event.Category.RELATIONSHIP, polarity=0,
        title=f"Target created: {target.name}", detail=f"Deadline {target.deadline.isoformat()}.", occurred_at=timezone.now())
    return {"id": target.id, "name": target.name}

@router.get("/fx/convert")
def convert_fx(request, amount: Decimal, base: str, quote: str):
    base, quote = base.upper(), quote.upper()
    if amount < 0:
        raise HttpError(422, "Amount cannot be negative.")
    if base == quote:
        return {"amount": str(amount), "base": base, "quote": quote, "rate": "1", "converted": str(amount), "source": "identity"}
    rate = FxRate.objects.filter(base=base, quote=quote).order_by("-fetched_at").first()
    if rate:
        value, source, used_rate = amount*rate.rate, rate.source, rate.rate
    else:
        inverse = FxRate.objects.filter(base=quote, quote=base).order_by("-fetched_at").first()
        if not inverse or not inverse.rate:
            raise HttpError(404, f"No exchange rate is available for {base}/{quote}.")
        used_rate = Decimal("1")/inverse.rate
        value, source = amount*used_rate, inverse.source
    return {"amount": str(amount), "base": base, "quote": quote, "rate": str(used_rate),
        "converted": str(value.quantize(Decimal("0.01"))), "source": source}

@router.post("/fx/rates")
def upsert_fx_rate(request, payload: FxRateIn):
    base, quote = payload.base.upper(), payload.quote.upper()
    if len(base) != 3 or len(quote) != 3 or base == quote or payload.rate <= 0:
        raise HttpError(422, "Use distinct three-letter currencies and a positive rate.")
    row, _ = FxRate.objects.update_or_create(base=base, quote=quote, defaults={
        "rate": payload.rate, "source": payload.source[:120], "fetched_at": timezone.now()})
    _recompute_client_scores()
    return {"base": row.base, "quote": row.quote, "rate": str(row.rate), "fetched_at": row.fetched_at.isoformat()}

@router.get("/calendar")
def calendar_items(request, month: str = ""):
    try:
        first = date.fromisoformat(f"{month}-01") if month else timezone.localdate().replace(day=1)
    except ValueError:
        raise HttpError(422, "Month must be YYYY-MM.")
    last = first.replace(day=monthrange(first.year, first.month)[1])
    items = []
    for inv in Invoice.objects.select_related("client").filter(due_date__range=(first, last)):
        if inv.status not in {Invoice.Status.PAID, Invoice.Status.WRITTEN_OFF}:
            items.append({"date": inv.due_date.isoformat(), "kind": "invoice", "title": inv.number, "client": inv.client.name, "status": inv.status})
    for inst in Instalment.objects.select_related("client", "invoice").filter(due_date__range=(first, last)):
        if inst.status not in {Instalment.Status.PAID, Instalment.Status.WAIVED}:
            items.append({"date": inst.due_date.isoformat(), "kind": "instalment", "title": f"{inst.invoice.number} · {inst.label}", "client": inst.client.name, "status": inst.status})
    return {"month": first.strftime("%Y-%m"), "items": sorted(items, key=lambda x: (x["date"], x["title"]))}


@router.get("/avoid")
def avoid_clients(request):
    from ledger.api import _client_snapshot
    from ledger.services.scoring import compute_client_score
    result = []
    for client in Client.objects.filter(status="blacklisted") | Client.objects.filter(score__lt=40):
        snapshot = _client_snapshot(client)
        score = compute_client_score(snapshot).as_dict()
        events = list(client.events.filter(deleted_at__isnull=True).order_by("-occurred_at")[:30])
        flags = [{"kind": e.kind, "title": e.title, "detail": e.detail, "occurred_at": e.occurred_at.isoformat()} for e in events if e.polarity < 0]
        for invoice in client.invoices.all():
            if invoice.status == Invoice.Status.DISPUTED:
                flags.append({"kind": "disputed_invoice", "title": f"Disputed invoice {invoice.number}", "detail": f"Invoice amount {invoice.amount} {invoice.currency}.", "occurred_at": invoice.updated_at.isoformat()})
            if invoice.status == Invoice.Status.WRITTEN_OFF:
                flags.append({"kind": "write_off", "title": f"Written off {invoice.number}", "detail": f"Invoice amount {invoice.amount} {invoice.currency}.", "occurred_at": invoice.updated_at.isoformat()})
        result.append({"id": client.id, "name": client.name, "company": client.company, "email": client.email,
            "status": client.status, "score": score["score"], "tier": score["tier"], "flags": flags[:20],
            "invoices": len(client.invoices.all()), "lifetime_collected": str(snapshot["lifetime_collected"]), "currency": snapshot["base_currency"]})
    unique = {item["id"]: item for item in result}
    return {"items": sorted(unique.values(), key=lambda item: item["score"])}


class InstalmentRowIn(Schema):
    seq: int
    label: str
    amount: Decimal
    due_date: date
    grace_days: int = 0

class PlanIn(Schema):
    invoice_id: int
    instalments: list[InstalmentRowIn]
    notes: str = ""

@router.post("/plans")
def create_plan(request, payload: PlanIn):
    if not payload.instalments:
        raise HttpError(422, "A plan must contain at least one instalment.")
    rows = sorted(payload.instalments, key=lambda item: item.seq)
    sequences = [item.seq for item in rows]
    if any(seq < 1 for seq in sequences) or len(set(sequences)) != len(sequences):
        raise HttpError(422, "Instalment sequence numbers must be unique positive integers.")
    if any(item.amount <= 0 or item.grace_days < 0 or item.grace_days > 60 for item in rows):
        raise HttpError(422, "Amounts must be positive and grace periods must be between 0 and 60 days.")
    if any(rows[index].due_date > rows[index + 1].due_date for index in range(len(rows)-1)):
        raise HttpError(422, "Instalment dates must be chronological.")
    with transaction.atomic():
        try:
            invoice = Invoice.objects.select_for_update().select_related("client").get(pk=payload.invoice_id)
        except Invoice.DoesNotExist:
            raise HttpError(404, "Invoice not found.")
        if invoice.status in {Invoice.Status.PAID, Invoice.Status.WRITTEN_OFF}:
            raise HttpError(422, "Paid or written-off invoices cannot receive a new plan.")
        if invoice.instalments.exists():
            raise HttpError(409, "This invoice already has an instalment plan.")
        paid = invoice.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        outstanding = max(Decimal("0"), invoice.amount-paid)
        if sum((item.amount for item in rows), Decimal("0")) != outstanding:
            raise HttpError(422, f"Instalment amounts must total the outstanding balance of {outstanding} {invoice.currency}.")
        for item in rows:
            Instalment.objects.create(invoice=invoice, client=invoice.client, seq=item.seq, label=item.label.strip()[:120],
                amount=item.amount, due_date=item.due_date, grace_days=item.grace_days)
        verdict = evaluate_plan_verdict([{"due_date": item.due_date, "amount": item.amount, "grace_days": item.grace_days, "status": "pending"} for item in rows])
        PlanMeta.objects.create(invoice=invoice, plan_deadline=max(item.due_date for item in rows), last_verdict=verdict, notes=payload.notes)
        Event.objects.create(client=invoice.client, engagement=invoice.engagement, invoice=invoice, kind="instalment_plan_created",
            category=Event.Category.MONEY, polarity=0, title=f"Instalment plan created for {invoice.number}",
            detail=f"{len(rows)} instalments scheduled; current verdict: {verdict}.", amount=outstanding, occurred_at=timezone.now())
        from ledger.api import _refresh_score
        score = _refresh_score(invoice.client)
    return {"invoice_id": invoice.id, "invoice_number": invoice.number, "verdict": verdict, "instalment_count": len(rows), "score": score.score}


DEFAULT_APP_SETTINGS = {
    "base_currency": "USD",
    "time_zone": "Africa/Kampala",
    "notifications_enabled": False,
    "sounds": {"success": True, "info": True, "warning": True, "alarm": True},
}

def _get_app_settings():
    import json
    from django.conf import settings as django_settings
    defaults = dict(DEFAULT_APP_SETTINGS)
    defaults["sounds"] = dict(DEFAULT_APP_SETTINGS["sounds"])
    defaults["base_currency"] = __import__("os").environ.get("LEDGER_BASE_CURRENCY", "USD").upper()
    defaults["time_zone"] = django_settings.TIME_ZONE
    row = Meta.objects.filter(pk="app_settings").first()
    if row:
        try:
            stored = json.loads(row.value)
            defaults.update({key: value for key, value in stored.items() if key in DEFAULT_APP_SETTINGS and key != "sounds"})
            if isinstance(stored.get("sounds"), dict):
                defaults["sounds"].update({key: bool(value) for key, value in stored["sounds"].items() if key in defaults["sounds"]})
        except (ValueError, TypeError):
            pass
    return defaults

@router.get("/settings")
def read_settings(request):
    return _get_app_settings()

@router.patch("/settings")
def update_settings(request, payload: SettingsIn):
    import json
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    values = _get_app_settings()
    previous_base_currency = values["base_currency"]
    changes = payload.dict(exclude_unset=True)
    if "base_currency" in changes and changes["base_currency"] is not None:
        currency = changes["base_currency"].upper()
        if len(currency) != 3 or not currency.isalpha():
            raise HttpError(422, "Base currency must be a three-letter currency code.")
        values["base_currency"] = currency
    if "time_zone" in changes and changes["time_zone"] is not None:
        try:
            ZoneInfo(changes["time_zone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise HttpError(422, "Unknown timezone.")
        values["time_zone"] = changes["time_zone"]
    if "notifications_enabled" in changes and changes["notifications_enabled"] is not None:
        values["notifications_enabled"] = bool(changes["notifications_enabled"])
    if "sounds" in changes and changes["sounds"] is not None:
        if not isinstance(changes["sounds"], dict):
            raise HttpError(422, "Sound preferences must be an object.")
        for key, value in changes["sounds"].items():
            if key not in values["sounds"]:
                raise HttpError(422, f"Unknown sound category: {key}.")
            values["sounds"][key] = bool(value)
    Meta.objects.update_or_create(key="app_settings", defaults={"value": json.dumps(values, sort_keys=True)})
    if values["base_currency"] != previous_base_currency:
        _recompute_client_scores()
    return values

@router.get("/notifications")
def list_notifications(request, since: datetime | None = None, limit: int = 30):
    limit = min(max(limit, 1), 100)
    if since is None:
        since = timezone.now() - __import__("datetime").timedelta(minutes=5)
    if timezone.is_naive(since):
        since = timezone.make_aware(since, timezone.get_current_timezone())
    kinds = ["invoice_overdue_reminder", "instalment_due_reminder", "payment_recorded", "ghosting_detected", "recurring_invoice_drafted",
        "plan_verdict_perfect", "plan_verdict_late", "plan_verdict_at_risk", "plan_verdict_broken"]
    rows = Event.objects.filter(kind__in=kinds, occurred_at__gt=since).order_by("occurred_at", "id")[:limit]
    return {"items": [{"id": e.id, "kind": e.kind, "title": e.title, "detail": e.detail,
        "category": e.category, "polarity": e.polarity, "occurred_at": e.occurred_at.isoformat()} for e in rows],
        "server_time": timezone.now().isoformat()}


@router.get("/clients/{client_id}/dossier.pdf")
def export_client_dossier(request, client_id: int):
    from django.conf import settings as django_settings
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from weasyprint import HTML
    from ledger.api import _client_snapshot
    from ledger.services.scoring import compute_client_score
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist:
        raise HttpError(404, "Client not found.")
    snapshot = _client_snapshot(client)
    score = compute_client_score(snapshot).as_dict()
    invoices = []
    for invoice in client.invoices.annotate(paid_total=Sum("payments__amount")).order_by("-issue_date"):
        paid = invoice.paid_total or Decimal("0")
        invoices.append({"number": invoice.number, "title": invoice.title, "due_date": invoice.due_date,
            "status": invoice.status, "currency": invoice.currency, "amount": invoice.amount,
            "outstanding": max(Decimal("0"), invoice.amount-paid)})
    events = list(client.events.filter(deleted_at__isnull=True).order_by("-occurred_at")[:250])
    html = render_to_string("ledger/client_dossier.html", {
        "client": client, "score": score, "invoices": invoices, "events": events,
        "currency": snapshot["base_currency"], "collected": f"{snapshot['lifetime_collected']:.2f}",
        "open_invoice_count": sum(1 for item in invoices if item["outstanding"] > 0),
        "generated_at": timezone.localtime().strftime("%Y-%m-%d %H:%M %Z"),
    })
    pdf = HTML(string=html, base_url=str(django_settings.BASE_DIR)).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="client-{client.id}-dossier.pdf"'
    return response

@router.get("/invoices/{invoice_id}/pdf")
def export_invoice_pdf(request, invoice_id: int):
    from django.conf import settings as django_settings
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from weasyprint import HTML
    try:
        invoice = Invoice.objects.select_related("client", "engagement").get(pk=invoice_id)
    except Invoice.DoesNotExist:
        raise HttpError(404, "Invoice not found.")
    paid = invoice.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    payments = list(invoice.payments.order_by("paid_on", "id"))
    instalments = list(invoice.instalments.order_by("seq"))
    html = render_to_string("ledger/invoice.html", {
        "invoice": invoice, "payments": payments, "instalments": instalments,
        "collected": f"{paid:.2f}", "outstanding": f"{max(Decimal('0'), invoice.amount-paid):.2f}",
        "generated_at": timezone.localtime().strftime("%Y-%m-%d %H:%M %Z"),
    })
    pdf = HTML(string=html, base_url=str(django_settings.BASE_DIR)).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{invoice.id}.pdf"'
    return response


@router.patch("/plans/{invoice_id}")
def update_plan(request, invoice_id: int, payload: PlanIn):
    if payload.invoice_id != invoice_id:
        raise HttpError(422, "Invoice ID in the request does not match the plan URL.")
    rows = sorted(payload.instalments, key=lambda item: item.seq)
    if not rows:
        raise HttpError(422, "A plan must contain at least one instalment.")
    sequences = [item.seq for item in rows]
    if any(seq < 1 for seq in sequences) or len(set(sequences)) != len(sequences):
        raise HttpError(422, "Instalment sequence numbers must be unique positive integers.")
    if any(item.amount <= 0 or item.grace_days < 0 or item.grace_days > 60 for item in rows):
        raise HttpError(422, "Amounts must be positive and grace periods must be between 0 and 60 days.")
    if any(rows[index].due_date > rows[index + 1].due_date for index in range(len(rows)-1)):
        raise HttpError(422, "Instalment dates must be chronological.")
    with transaction.atomic():
        try:
            invoice = Invoice.objects.select_for_update().select_related("client").get(pk=invoice_id)
        except Invoice.DoesNotExist:
            raise HttpError(404, "Invoice not found.")
        if invoice.status in {Invoice.Status.PAID, Invoice.Status.WRITTEN_OFF}:
            raise HttpError(422, "Paid or written-off invoices cannot have their plans edited.")
        existing = list(invoice.instalments.all())
        if PaymentAllocation.objects.filter(instalment__in=existing).exists() or any(row.status == Instalment.Status.PAID or row.paid_on for row in existing):
            raise HttpError(409, "A plan with allocated payments cannot be edited; preserve its financial history.")
        paid = invoice.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        outstanding = max(Decimal("0"), invoice.amount-paid)
        if sum((item.amount for item in rows), Decimal("0")) != outstanding:
            raise HttpError(422, f"Instalment amounts must total the outstanding balance of {outstanding} {invoice.currency}.")
        previous_verdict = evaluate_plan_verdict([{"due_date": row.due_date, "paid_on": row.paid_on,
            "status": row.status, "grace_days": row.grace_days, "amount": row.amount} for row in existing]) if existing else None
        for row in existing:
            row.soft_delete()
        for item in rows:
            Instalment.objects.create(invoice=invoice, client=invoice.client, seq=item.seq, label=item.label.strip()[:120],
                amount=item.amount, due_date=item.due_date, grace_days=item.grace_days)
        verdict = evaluate_plan_verdict([{"due_date": item.due_date, "amount": item.amount, "grace_days": item.grace_days, "status": "pending"} for item in rows])
        meta = PlanMeta.all_objects.filter(invoice=invoice).first()
        if meta:
            meta.deleted_at = None
            meta.plan_deadline = max(item.due_date for item in rows)
            meta.last_verdict = verdict
            meta.notes = payload.notes
            meta.save()
        else:
            PlanMeta.objects.create(invoice=invoice, plan_deadline=max(item.due_date for item in rows), last_verdict=verdict, notes=payload.notes)
        Event.objects.create(client=invoice.client, engagement=invoice.engagement, invoice=invoice, kind="instalment_plan_updated",
            category=Event.Category.MONEY, polarity=0, title=f"Instalment plan updated for {invoice.number}",
            detail=f"Previous verdict: {previous_verdict or 'none'}; new verdict: {verdict}; {len(rows)} instalments scheduled.",
            amount=outstanding, occurred_at=timezone.now())
        from ledger.api import _refresh_score
        score = _refresh_score(invoice.client)
    return {"invoice_id": invoice.id, "invoice_number": invoice.number, "verdict": verdict, "instalment_count": len(rows), "score": score.score}
