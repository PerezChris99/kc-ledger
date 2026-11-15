"""KC Ledger API; hide Django admin from the native desktop process."""

import os

from django.contrib import admin
from django.urls import path, re_path
from ledger.api import router
from ledger.api_extra import router as extra_router
from ledger.cron_views import daily
from ledger.security import staff_session_auth
from ledger.update_manifest_views import latest
from ledger.update_views import updates
from ledger.version_views import version
from ninja import NinjaAPI

from config.version import build_info

api = NinjaAPI(title="KC Ledger API", version=build_info()["version"], auth=staff_session_auth)
api.add_router("/", router)
api.add_router("/", extra_router)

urlpatterns = [
    path("api/version", version),
    path("api/internal/cron/daily", daily),
    path("api/desktop/updates", updates),
    path("downloads/latest.json", latest),
    path("downloads/beta.json", latest, {"channel": "beta"}),
    path("api/", api.urls),
]
if os.environ.get("LEDGER_DESKTOP") == "1":
    from ledger.desktop_views import serve_frontend

    urlpatterns.append(re_path(r"^(?P<path>.*)$", serve_frontend))
else:
    urlpatterns.insert(0, path("admin/", admin.site.urls))
