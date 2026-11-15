"""KC Ledger API; hide Django admin from the native desktop process."""

import os

from django.contrib import admin
from django.urls import path, re_path
from ledger.api import router
from ledger.api_extra import router as extra_router
from ledger.security import staff_session_auth
from ninja import NinjaAPI

api = NinjaAPI(title="KC Ledger API", version="0.1.0", auth=staff_session_auth)
api.add_router("/", router)
api.add_router("/", extra_router)

urlpatterns = [path("api/", api.urls)]
if os.environ.get("LEDGER_DESKTOP") == "1":
    from ledger.desktop_views import serve_frontend

    urlpatterns.append(re_path(r"^(?P<path>.*)$", serve_frontend))
else:
    urlpatterns.insert(0, path("admin/", admin.site.urls))
