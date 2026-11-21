"""Freeze strategy results at review time rather than rewriting history.

Historical rows intentionally remain unmeasured. They cannot be backfilled from
today's figures without manufacturing their actual past review snapshots.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ledger", "0007_business_intelligence")]

    operations = [
        migrations.AddField(
            model_name="businessstrategydecision",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="businessstrategydecision",
            name="review_value",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=18, null=True
            ),
        ),
        migrations.AddField(
            model_name="businessstrategydecision",
            name="review_change",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=18, null=True
            ),
        ),
        migrations.AddField(
            model_name="businessstrategydecision",
            name="review_favorable",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="businessstrategydecision",
            name="review_quality",
            field=models.CharField(default="not_reviewed", max_length=24),
        ),
    ]
