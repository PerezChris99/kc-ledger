"""Protected Vercel Cron entry point with a PostgreSQL-wide advisory lock."""

import logging
import os
import secrets

from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from ledger import jobs

logger = logging.getLogger(__name__)
LOCK_ID = 2010170701


@require_GET
def daily(request):
    if os.environ.get("LEDGER_DEPLOYMENT") != "vercel":
        return HttpResponse(status=404)
    expected = os.environ.get("CRON_SECRET", "")
    supplied = request.headers.get("Authorization", "")
    if len(expected) < 32 or not secrets.compare_digest(supplied, "Bearer " + expected):
        return HttpResponse(status=403)
    if connection.vendor != "postgresql":
        return JsonResponse({"status": "database_unavailable"}, status=503)

    # Transaction-scoped advisory locks work through managed Postgres
    # transaction poolers, unlike session-scoped advisory locks.
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [LOCK_ID])
                acquired = cursor.fetchone()[0]
            if not acquired:
                return JsonResponse({"status": "already_running"}, status=409)
            jobs.refresh_instalment_states()
            jobs.emit_due_reminders()
            jobs.detect_ghosting()
            jobs.draft_recurring_invoices()
            jobs.refresh_fx_rates()
            jobs.update_client_intelligence()
        return JsonResponse({"status": "ok"})
    except Exception:
        logger.exception("Cron job failure")
        return JsonResponse({"status": "failed"}, status=500)
    finally:
        connection.close()
