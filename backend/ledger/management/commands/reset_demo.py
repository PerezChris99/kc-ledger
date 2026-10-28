from django.core.management.base import BaseCommand
from django.utils import timezone
from ledger.models import Client, Engagement, Expense, Instalment, Invoice, Payment, Target, TimeEntry

class Command(BaseCommand):
    help = "Soft-delete demo records only; append-only audit events remain intact."

    def handle(self, *args, **options):
        now = timezone.now()
        clients = Client.all_objects.filter(email__endswith="@example.test", deleted_at__isnull=True)
        ids = list(clients.values_list("id", flat=True))
        if not ids:
            self.stdout.write("No live demo records found.")
            return
        engagements = Engagement.all_objects.filter(client_id__in=ids, deleted_at__isnull=True)
        invoices = Invoice.all_objects.filter(client_id__in=ids, deleted_at__isnull=True)
        invoice_ids = list(invoices.values_list("id", flat=True))
        instalments = Instalment.all_objects.filter(invoice_id__in=invoice_ids, deleted_at__isnull=True)
        payments = Payment.all_objects.filter(invoice_id__in=invoice_ids, deleted_at__isnull=True)
        expenses = Expense.all_objects.filter(client_id__in=ids, deleted_at__isnull=True)
        time_entries = TimeEntry.all_objects.filter(client_id__in=ids, deleted_at__isnull=True)
        for queryset in (instalments, payments, expenses, time_entries, invoices, engagements, clients):
            queryset.update(deleted_at=now)
        self.stdout.write(self.style.SUCCESS(f"Soft-deleted demo records for {len(ids)} clients. Audit events were preserved."))
