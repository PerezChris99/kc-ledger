from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from ledger.api import router

api = NinjaAPI(title="KC Ledger API", version="0.1.0", csrf=True)
api.add_router("/", router)
urlpatterns = [path("admin/", admin.site.urls), path("api/", api.urls)]
