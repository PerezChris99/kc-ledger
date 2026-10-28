from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from ledger.models import Client, Engagement, Event, Instalment, Invoice, Payment, PaymentAllocation, SignalType
from ledger.services.scoring import compute_client_score

DEMO = [
    ("Nadia Raman", "Nadia Studio", "nadia@example.test", "active", 4200),
    ("Marcus Bell", "Bell Works", "marcus@example.test", "active", 2800),
    ("Priya Shah", "Priya Digital", "priya@example.test", "active", 6400),
    ("Dmitri Volkov", "Volkov Systems", "dmitri@example.test", "active", 1900),
    ("Amanda Cole", "Cole Partners", "amanda@example.test", "blacklisted", 9000),
    ("Tobias Grant", "Grant Labs", "tobias@example.test", "active", 3500),
]

class Command(BaseCommand):
    help = "Create a repeatable fictional demo dataset using example.test addresses."

    def handle(self, *args, **options):
        today = timezone.localdate()
        signals = [
            ("payment_on_time", "Payment on time", "money", 1, "1"),
            ("payment_late", "Payment late", "money", -1, "1"),
            ("scope_creep", "Unapproved scope increase", "delivery", -1, "2"),
            ("rate_haggling", "Rate haggling", "behaviour", -1, "1"),
            ("abusive", "Abusive communication", "comms", -1, "3"),
            ("chargeback", "Chargeback", "money", -1, "3"),
            ("rate_increase_accepted", "Rate increase accepted", "money", 1, "1"),
        ]
        for kind, label, category, polarity, weight in signals:
            SignalType.objects.update_or_create(kind=kind, defaults={"label": label, "category": category, "polarity": polarity, "weight": Decimal(weight)})
        for index, (name, company, email, status, amount) in enumerate(DEMO, start=1):
            client, _ = Client.objects.get_or_create(email=email, defaults={"name": name, "company": company, "currency": "USD", "status": status, "started_at": today-timedelta(days=180*index), "notes": "Fictional demo record; not a real client."})
            engagement, _ = Engagement.objects.get_or_create(client=client, name=f"{company} service", defaults={"kind": "fixed", "agreed_amount": Decimal(amount), "currency": "USD", "status": "active"})
            overdue = index in (4, 5)
            invoice, _ = Invoice.objects.get_or_create(number=f"DEMO-{index:03d}", defaults={"client": client, "engagement": engagement, "title": f"{company} project milestone", "issue_date": today-timedelta(days=45), "due_date": today-timedelta(days=15 if overdue else -10), "amount": Decimal(amount), "currency": "USD", "status": "sent"})
            instalment, _ = Instalment.objects.get_or_create(invoice=invoice, seq=1, defaults={"client": client, "label": "Full payment", "amount": invoice.amount, "due_date": invoice.due_date, "status": "pending"})
            if not overdue:
                payment, created = Payment.objects.get_or_create(invoice=invoice, reference=f"DEMO-PAY-{index:03d}", defaults={"client": client, "amount": invoice.amount, "paid_on": today-timedelta(days=20), "method": "demo"})
                if created:
                    PaymentAllocation.objects.create(payment=payment, instalment=instalment, amount=payment.amount)
                    instalment.status = "paid"
                    instalment.paid_on = payment.paid_on
                    instalment.save(update_fields=["status", "paid_on", "updated_at"])
                    invoice.status = "paid"
                    invoice.paid_at = timezone.now()
                    invoice.save(update_fields=["status", "paid_at", "updated_at"])
                    Event.objects.create(client=client, invoice=invoice, payment=payment, kind="payment_recorded", category="money", polarity=1, title="Demo payment recorded", detail="Fictional seeded payment.", amount=payment.amount, occurred_at=timezone.now())
            if index in (3, 4):
                Event.objects.get_or_create(client=client, kind="scope_creep", title="Demo risk signal", defaults={"category": "delivery", "polarity": -1, "weight": Decimal("2"), "detail": "Fictional seed signal.", "occurred_at": timezone.now()})
            snapshot = {"status": client.status, "invoices": [{"amount": invoice.amount, "status": invoice.status, "due_date": invoice.due_date}], "lifetime_collected": invoice.amount if invoice.status == "paid" else 0, "engagement_count": 1, "started_at": client.started_at}
            client.score = compute_client_score(snapshot).score
            client.score_updated_at = timezone.now()
            client.save(update_fields=["score", "score_updated_at", "updated_at"])
        self.stdout.write(self.style.SUCCESS("Demo dataset ready; all demo addresses use example.test."))
