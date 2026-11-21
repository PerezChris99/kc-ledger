"""Add a controlled vocabulary for structured client behaviour evidence."""

from decimal import Decimal

from django.db import migrations

SIGNALS = [
    ("late_feedback", "Slow feedback / approval", "comms", -1, 1),
    ("missed_meeting", "Missed scheduled meeting", "comms", -1, 1),
    ("unapproved_revisions", "Unapproved revisions", "delivery", -1, 2),
    ("missed_deadline", "Client missed agreed deadline", "delivery", -1, 2),
    ("ghosting_detected", "Communication gap recorded", "comms", -1, 2),
    ("contract_dispute", "Contract terms disputed", "relationship", -1, 4),
    ("invoice_overdue", "Open invoice past due", "money", -1, 3),
    ("invoice_disputed", "Invoice dispute", "money", -1, 3),
    ("invoice_written_off", "Written-off invoice", "money", -1, 4),
    ("clear_feedback", "Timely, clear feedback", "comms", 1, 1),
    ("scope_respected", "Scope and change control respected", "delivery", 1, 1),
    ("repeat_engagement", "Repeat engagement", "relationship", 1, 1),
]


def add_signals(apps, schema_editor):
    types = apps.get_model("ledger", "SignalType")
    for kind, label, category, polarity, weight in SIGNALS:
        types.objects.update_or_create(
            kind=kind,
            defaults={
                "label": label,
                "category": category,
                "polarity": polarity,
                "weight": Decimal(weight),
                "icon": "",
            },
        )


def remove_signals(apps, schema_editor):
    types = apps.get_model("ledger", "SignalType")
    types.objects.filter(kind__in=[row[0] for row in SIGNALS]).delete()


class Migration(migrations.Migration):
    dependencies = [("ledger", "0005_client_intelligence")]
    operations = [migrations.RunPython(add_signals, remove_signals)]
