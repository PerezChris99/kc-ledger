from django.core.management.base import BaseCommand
from ledger.models import Client
from ledger.api import _refresh_score

class Command(BaseCommand):
    help = "Recompute and persist explainable client health scores for every active client."

    def handle(self, *args, **options):
        count = 0
        for client in Client.objects.all().iterator():
            _refresh_score(client)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Recomputed scores for {count} clients."))
