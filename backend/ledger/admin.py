from django.contrib import admin
from .models import Client, Engagement, Invoice, Instalment, PlanMeta, Payment, PaymentAllocation, Expense, Event, SignalType, TimeEntry, Target, FxRate, Meta

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "status", "score", "currency", "updated_at")
    list_filter = ("status", "country", "currency")
    search_fields = ("name", "company", "email")
    readonly_fields = ("score_updated_at", "created_at", "updated_at", "deleted_at")

@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    list_display = ("name", "client", "kind", "status", "agreed_amount", "currency")
    list_filter = ("kind", "status", "currency")
    search_fields = ("name", "client__name")

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "title", "amount", "currency", "status", "due_date")
    list_filter = ("status", "currency", "due_date")
    search_fields = ("number", "title", "client__name")
    readonly_fields = ("created_at", "updated_at", "deleted_at")

@admin.register(Instalment)
class InstalmentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "seq", "label", "amount", "due_date", "status")
    list_filter = ("status", "due_date")
    search_fields = ("invoice__number", "client__name")

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "client", "amount", "paid_on", "method", "reference")
    list_filter = ("method", "paid_on")
    search_fields = ("invoice__number", "client__name", "reference")

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("category", "amount", "currency", "spent_on", "client", "billable")
    list_filter = ("category", "billable", "currency", "spent_on")

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "category", "polarity", "occurred_at")
    list_filter = ("category", "polarity", "occurred_at")
    search_fields = ("title", "detail", "client__name")
    readonly_fields = tuple(field.name for field in Event._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

for model in (PlanMeta, PaymentAllocation, SignalType, TimeEntry, Target, FxRate, Meta):
    admin.site.register(model)
