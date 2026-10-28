from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from ninja.security import django_auth
from ledger.api import router
from ledger.api_extra import router as extra_router

api = NinjaAPI(title="KC Ledger API", version="0.1.0", auth=django_auth, csrf=True)
api.add_router("/", router)
api.add_router("/", extra_router)
urlpatterns = [path("admin/", admin.site.urls), path("api/", api.urls)]
