import json
import logging
import os
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from apscheduler.schedulers.background import BackgroundScheduler
from django.db import transaction
from django.utils import timezone

from ledger.models import Client, Engagement, Event, FxRate, Instalment, Invoice, PlanMeta
from ledger.services.instalments import evaluate_plan_verdict

logger = logging.getLogger(__name__)
_scheduler = None


def refresh_instalment_states():
    today = timezone.localdate()
    for row in Instalment.objects.select_related("invoice", "client").filter(status__in=["pending", "late", "overdue"]):
        next_status = row.status
        if today > row.due_date + timedelta(days=row.grace_days + 30):
            next_status = Instalment.Status.MISSED
        elif today > row.due_date + timedelta(days=row.grace_days):
            next_status = Instalment.Status.OVERDUE
        if next_status != row.status:
            row.status = next_status
            row.save(update_fields=["status", "updated_at"])
    invoice_ids = set(Instalment.objects.values_list("invoice_id", flat=True).distinct())
    for invoice_id in invoice_ids:
        invoice = Invoice.objects.select_related("client").filter(pk=invoice_id).first()
        if not invoice:
            continue
        rows = list(invoice.instalments.all())
        if not rows:
            continue
        verdict = evaluate_plan_verdict([{"due_date": r.due_date, "paid_on": r.paid_on, "status": r.status,
            "grace_days": r.grace_days, "amount": r.amount} for r in rows])
        with transaction.atomic():
            meta = PlanMeta.objects.filter(invoice=invoice).first()
            if not meta or meta.last_verdict == verdict:
                continue
            previous = meta.last_verdict
            meta.last_verdict = verdict
            meta.save(update_fields=["last_verdict", "updated_at"])
            polarity = 1 if verdict == "perfect" else -1 if verdict in {"late", "at_risk", "broken"} else 0
            Event.objects.create(client=invoice.client, engagement=invoice.engagement, invoice=invoice,
                kind=f"plan_verdict_{verdict}", category=Event.Category.MONEY, polarity=polarity,
                title=f"Plan verdict changed: {verdict.replace('_', ' ')}",
                detail=f"{invoice.number}: {previous or 'uninitialised'} → {verdict}.", occurred_at=timezone.now())
            from ledger.api import _refresh_score
            _refresh_score(invoice.client)


def emit_due_reminders():
    now = timezone.now()
    today = timezone.localdate()
    for invoice in Invoice.objects.select_related("client").filter(due_date__lt=today).exclude(status__in=["paid", "written_off"]):
        if not Event.objects.filter(invoice=invoice, kind="invoice_overdue_reminder", occurred_at__date=today).exists():
            Event.objects.create(client=invoice.client, engagement=invoice.engagement, invoice=invoice,
                kind="invoice_overdue_reminder", category=Event.Category.MONEY, polarity=-1,
                title=f"Invoice overdue: {invoice.number}", detail=f"Outstanding invoice is past due since {invoice.due_date}.",
                amount=invoice.amount, occurred_at=now)
    for instalment in Instalment.objects.select_related("invoice", "client").filter(
        due_date__range=(today, today + timedelta(days=3))
    ).exclude(status__in=["paid", "waived"]):
        if not Event.objects.filter(invoice=instalment.invoice, kind="instalment_due_reminder", occurred_at__date=today, detail__contains=instalment.label).exists():
            Event.objects.create(client=instalment.client, invoice=instalment.invoice, kind="instalment_due_reminder",
                category=Event.Category.MONEY, polarity=0, title=f"Instalment due: {instalment.invoice.number}",
                detail=f"{instalment.label} is due on {instalment.due_date}.", amount=instalment.amount, occurred_at=now)


def detect_ghosting():
    today = timezone.localdate()
    for client in Client.objects.filter(status=Client.Status.ACTIVE):
        if not client.engagements.filter(status=Engagement.Status.ACTIVE).exists():
            continue
        last_comms = Event.objects.filter(client=client, category=Event.Category.COMMS).order_by("-occurred_at").first()
        reference = last_comms.occurred_at.date() if last_comms else (client.started_at or client.created_at.date())
        silence_days = (today - reference).days
        if silence_days < 30:
            continue
        latest_signal = Event.objects.filter(client=client, kind="ghosting_detected").order_by("-occurred_at").first()
        if latest_signal and (timezone.now() - latest_signal.occurred_at).days < 7:
            continue
        Event.objects.create(client=client, kind="ghosting_detected", category=Event.Category.COMMS,
            polarity=-1, weight=Decimal("1"), title="No recent communication recorded",
            detail=f"No communication event has been recorded for {silence_days} days. Review manually; this is a signal, not proof of ghosting.",
            occurred_at=timezone.now())


def draft_recurring_invoices():
    today = timezone.localdate()
    for engagement in Engagement.objects.select_related("client").filter(
        kind=Engagement.Kind.RETAINER, status=Engagement.Status.ACTIVE,
        recurring_interval_days__gt=0, next_invoice_date__lte=today
    ):
        number = f"RET-{engagement.id}-{today.strftime('%Y%m%d')}"
        invoice, created = Invoice.all_objects.get_or_create(number=number, defaults={
            "client": engagement.client, "engagement": engagement, "title": f"{engagement.name} retainer",
            "issue_date": today, "due_date": today + timedelta(days=14),
            "amount": engagement.agreed_amount, "currency": engagement.currency, "status": Invoice.Status.DRAFT,
            "notes": "Automatically drafted recurring invoice; review before sending."
        })
        if invoice.deleted_at:
            invoice.deleted_at = None
            invoice.save(update_fields=["deleted_at", "updated_at"])
        engagement.next_invoice_date = today + timedelta(days=engagement.recurring_interval_days)
        engagement.save(update_fields=["next_invoice_date", "updated_at"])
        if created:
            Event.objects.create(client=engagement.client, engagement=engagement, invoice=invoice,
                kind="recurring_invoice_drafted", category=Event.Category.MONEY, polarity=0,
                title=f"Recurring invoice drafted: {invoice.number}", detail="Review the draft before sending.",
                amount=invoice.amount, occurred_at=timezone.now())


def refresh_fx_rates():
    access_key = os.environ.get("EXCHANGERATE_HOST_ACCESS_KEY", "").strip()
    if not access_key:
        logger.info("FX refresh skipped: EXCHANGERATE_HOST_ACCESS_KEY is not configured.")
        return
    currencies = os.environ.get("LEDGER_FX_CURRENCIES", "EUR,GBP,UGX,CAD,AUD,JPY,CHF").upper()
    query = urlencode({"access_key": access_key, "source": "USD", "currencies": currencies})
    request = Request(f"https://api.exchangerate.host/live?{query}", headers={"User-Agent": "KC-Ledger/0.1"})
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("success"):
            logger.warning("FX refresh failed: provider returned an unsuccessful response.")
            return
        quotes = payload.get("quotes", {})
        now = timezone.now()
        for key, value in quotes.items():
            if key.startswith("USD") and len(key) == 6 and Decimal(str(value)) > 0:
                FxRate.objects.update_or_create(base="USD", quote=key[3:], defaults={
                    "rate": Decimal(str(value)), "fetched_at": now, "source": "exchangerate.host"
                })
    except Exception:
        logger.exception("FX refresh failed; existing stored rates were retained.")


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone=timezone.get_current_timezone_name())
    _scheduler.add_job(refresh_instalment_states, "interval", minutes=1, id="instalment-state", replace_existing=True, max_instances=1, coalesce=True)
    _scheduler.add_job(emit_due_reminders, "interval", minutes=5, id="due-reminders", replace_existing=True, max_instances=1, coalesce=True)
    _scheduler.add_job(detect_ghosting, "cron", hour=8, minute=0, id="ghosting", replace_existing=True, max_instances=1, coalesce=True)
    _scheduler.add_job(draft_recurring_invoices, "cron", hour=6, minute=0, id="recurring-invoices", replace_existing=True, max_instances=1, coalesce=True)
    _scheduler.add_job(refresh_fx_rates, "cron", hour=7, minute=0, id="fx-refresh", replace_existing=True, max_instances=1, coalesce=True)
    _scheduler.start()
    logger.info("KC Ledger background scheduler started.")
