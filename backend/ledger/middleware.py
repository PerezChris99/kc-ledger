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
