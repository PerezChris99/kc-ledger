from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from ledger.models import Client, Event, Expense, FxRate, Instalment, Invoice, Payment, Target, TimeEntry

router = Router()

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
    base = __import__("os").environ.get("LEDGER_BASE_CURRENCY", "USD").upper()
    today = timezone.localdate()
    buckets = {"not_due": Decimal("0"), "1_30": Decimal("0"), "31_60": Decimal("0"), "61_plus": Decimal("0")}
    currency_gaps = set()
    concentration = {}
    for invoice in Invoice.objects.select_related("client").all():
        paid = invoice.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
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

@router.get("/targets")
def list_targets(request):
    return {"items": [{"id": t.id, "name": t.name, "type": t.type, "amount": str(t.amount),
        "currency": t.currency, "deadline": t.deadline.isoformat(), "created_at": t.created_at.isoformat()}
        for t in Target.objects.order_by("deadline")]}

@router.post("/targets")
def create_target(request, payload: TargetIn):
    if payload.amount <= 0:
        raise HttpError(422, "Target amount must be positive.")
    if payload.type not in {"revenue", "clients", "hours"}:
        raise HttpError(422, "Unsupported target type.")
    target = Target.objects.create(**payload.dict())
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
        score = compute_client_score(_client_snapshot(client)).as_dict()
        events = list(client.events.filter(deleted_at__isnull=True).order_by("-occurred_at")[:30])
        flags = [{"kind": e.kind, "title": e.title, "detail": e.detail, "occurred_at": e.occurred_at.isoformat()} for e in events if e.polarity < 0]
        for invoice in client.invoices.all():
            if invoice.status == Invoice.Status.DISPUTED:
                flags.append({"kind": "disputed_invoice", "title": f"Disputed invoice {invoice.number}", "detail": f"Invoice amount {invoice.amount} {invoice.currency}.", "occurred_at": invoice.updated_at.isoformat()})
            if invoice.status == Invoice.Status.WRITTEN_OFF:
                flags.append({"kind": "write_off", "title": f"Written off {invoice.number}", "detail": f"Invoice amount {invoice.amount} {invoice.currency}.", "occurred_at": invoice.updated_at.isoformat()})
        result.append({"id": client.id, "name": client.name, "company": client.company, "email": client.email,
            "status": client.status, "score": score["score"], "tier": score["tier"], "flags": flags[:20],
            "invoices": len(client.invoices.all()), "lifetime_collected": str(sum((p.amount for p in client.payments.all()), Decimal("0")))})
    unique = {item["id"]: item for item in result}
    return {"items": sorted(unique.values(), key=lambda item: item["score"])}
