"""Authenticated desktop update preferences and check state."""

import os

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect

from ledger.security import staff_session_auth


@csrf_protect
@require_http_methods(["GET", "POST"])
def updates(request):
    if os.environ.get("LEDGER_DESKTOP") != "1":
        return JsonResponse({"detail": "Native desktop only"}, status=404)
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"detail": "Authentication required"}, status=403)
    from desktop import updater

    if request.method == "POST":
        import json

        try:
            payload = json.loads(request.body)
            if payload.get("action") == "check":
                updater.check_in_background()
                return JsonResponse({"status": "checking"})
            updater.save_settings(payload["policy"], payload["channel"])
        except (KeyError, ValueError, json.JSONDecodeError):
            return JsonResponse({"detail": "Invalid update policy"}, status=422)
    return JsonResponse(updater.settings())
