"""Document real proposals and outcomes before estimating conversion."""

from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ledger", "0008_strategy_review_evidence")]

    operations = [
        migrations.CreateModel(
            name="BusinessOpportunity",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=160)),
                (
                    "source",
                    models.CharField(
                        max_length=16,
                        default="unknown",
                        choices=[
                            ("referral", "Referral"),
                            ("inbound", "Inbound"),
                            ("outbound", "Outbound"),
                            ("repeat", "Repeat buyer"),
                            ("other", "Other"),
                            ("unknown", "Unknown"),
                        ],
                    ),
                ),
                (
                    "stage",
                    models.CharField(
                        max_length=16,
                        default="discovered",
                        choices=[
                            ("discovered", "Discovered"),
                            ("contacted", "Contacted"),
                            ("qualified", "Qualified"),
                            ("proposed", "Proposal sent"),
                            ("negotiating", "Negotiating"),
                            ("won", "Won"),
                            ("lost", "Lost"),
                            ("archived", "Archived"),
                        ],
                    ),
                ),
                (
                    "proposed_amount",
                    models.DecimalField(max_digits=18, decimal_places=2, default=Decimal(0)),
                ),
                ("currency", models.CharField(max_length=3, default="USD")),
                ("opened_on", models.DateField()),
                ("closed_on", models.DateField(blank=True, null=True)),
                ("next_action", models.CharField(blank=True, max_length=280)),
                ("lost_reason", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        to="ledger.client",
                        null=True,
                        blank=True,
                        related_name="business_opportunities",
                        on_delete=django.db.models.deletion.SET_NULL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["stage", "opened_on"], name="pipeline_stage_open_idx"),
                    models.Index(fields=["source", "stage"], name="pipeline_source_stage_idx"),
                ],
            },
        ),
    ]
