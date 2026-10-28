from decimal import Decimal
from django.db import migrations


def seed_signal_types(apps, schema_editor):
    SignalType = apps.get_model("ledger", "SignalType")
    rows = [
        ("payment_on_time", "Payment on time", "money", 1, Decimal("1")),
        ("payment_late", "Payment late", "money", -1, Decimal("1")),
        ("scope_creep", "Unapproved scope increase", "delivery", -1, Decimal("2")),
        ("rate_haggling", "Rate haggling", "behaviour", -1, Decimal("1")),
        ("abusive", "Abusive communication", "comms", -1, Decimal("3")),
        ("chargeback", "Chargeback", "money", -1, Decimal("3")),
        ("rate_increase_accepted", "Rate increase accepted", "money", 1, Decimal("1")),
    ]
    for kind, label, category, polarity, weight in rows:
        SignalType.objects.update_or_create(kind=kind, defaults={
            "label": label, "category": category, "polarity": polarity, "weight": weight, "icon": ""
        })


def remove_signal_types(apps, schema_editor):
    SignalType = apps.get_model("ledger", "SignalType")
    SignalType.objects.filter(kind__in=[
        "payment_on_time", "payment_late", "scope_creep", "rate_haggling",
        "abusive", "chargeback", "rate_increase_accepted"
    ]).delete()


class Migration(migrations.Migration):
    dependencies = [("ledger", "0001_initial")]
    operations = [migrations.RunPython(seed_signal_types, remove_signal_types)]
