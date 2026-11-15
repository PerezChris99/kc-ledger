"""Bound API request sizes on both Docker and native desktop runtimes."""

from django.http import HttpResponse, HttpResponseBadRequest


class ApiRequestLimitsMiddleware:
    MAX_JSON_BYTES = 1_048_576
    MAX_QUERY_BYTES = 4_096

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            query = request.META.get("QUERY_STRING", "")
            if len(query.encode("utf-8")) > self.MAX_QUERY_BYTES:
                return HttpResponse("Query string too long.", status=414)
            raw_length = request.META.get("CONTENT_LENGTH", "")
            if raw_length:
                try:
                    length = int(raw_length)
                except (ValueError, TypeError):
                    return HttpResponseBadRequest("Invalid request length.")
                if length < 0:
                    return HttpResponseBadRequest("Invalid request length.")
                if length > self.MAX_JSON_BYTES:
                    return HttpResponse("Request body too large.", status=413)
        return self.get_response(request)


class DatabaseCutoverGuardMiddleware:
    """Fail closed before serving a legacy SQLite ledger against fresh PostgreSQL."""

    def __init__(self, get_response):
        from ledger.management.commands.check_db_transition import Command

        # Runs once per server process, not on every request.
        Command().handle()
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)


class MinimumVersionMiddleware:
    """Block financial API writes after a trusted mandatory desktop update."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import json
        import os
        from pathlib import Path

        if os.environ.get("LEDGER_DESKTOP") != "1":
            return self.get_response(request)
        path = request.path
        if not path.startswith("/api/") or path.startswith(
            (
                "/api/auth/",
                "/api/csrf",
                "/api/session",
                "/api/version",
                "/api/health",
                "/api/desktop/updates",
            )
        ):
            return self.get_response(request)
        root = Path(os.environ.get("LOCALAPPDATA", "")) / "KCLedger"
        marker = root / "update-required.json"
        if marker.exists():
            from config.version import build_info
            from django.http import JsonResponse

            from desktop.updater import version_tuple

            data = json.loads(marker.read_text(encoding="utf-8"))
            if version_tuple(build_info()["version"]) < version_tuple(
                data["min_supported_version"]
            ):
                return JsonResponse(
                    {"detail": "A mandatory signed KC Ledger update is required."},
                    status=426,
                )
        return self.get_response(request)
