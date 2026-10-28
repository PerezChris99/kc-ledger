from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ledger", "0002_seed_signal_types")]
    operations = [
        migrations.AddField(
            model_name="engagement",
            name="recurring_interval_days",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="engagement",
            name="next_invoice_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
