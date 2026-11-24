import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Sum

from ledger.models import Invoice


class Command(BaseCommand):
    help = "Compare invoice balances by number and currency against an independent opening or closing CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "statement", help="UTF-8 CSV with invoice,currency,outstanding for every open invoice"
        )

    def handle(self, *args, **options):
        expected = {}
        try:
            with open(options["statement"], encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames != ["invoice", "currency", "outstanding"]:
                    raise CommandError("Expected header: invoice,currency,outstanding")
                for row in reader:
                    key = (row["invoice"].strip(), row["currency"].strip().upper())
                    amount = Decimal(row["outstanding"])
                    if not key[0] or key in expected or not amount.is_finite() or amount <= 0:
                        raise CommandError(
                            f"Invalid or duplicate open balance at line {reader.line_num}"
                        )
                    expected[key] = amount
        except (OSError, InvalidOperation, TypeError, AttributeError) as exc:
            raise CommandError("Unable to read the supplied statement.") from exc
        actual = {}
        invoices = Invoice.objects.exclude(status=Invoice.Status.WRITTEN_OFF).annotate(
            received=Sum("payments__amount", filter=Q(payments__deleted_at__isnull=True))
        )
        for invoice in invoices:
            balance = invoice.amount - (invoice.received or Decimal(0))
            if balance:
                actual[invoice.number, invoice.currency] = balance
        mismatches = [
            key
            for key in sorted(actual.keys() | expected.keys())
            if actual.get(key) != expected.get(key)
        ]
        for key in mismatches:
            self.stderr.write(
                f"{key[0]} ({key[1]}): ledger={actual.get(key, 0)}, statement={expected.get(key, 0)}"
            )
        if mismatches:
            raise CommandError(f"{len(mismatches)} invoice balance(s) differ.")
        self.stdout.write(f"Matched {len(actual)} open invoice balance(s).")
