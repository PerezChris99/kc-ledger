"""Owner goals, recorded strategies, and optional business second opinions."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ledger", "0006_signal_vocabulary")]

    operations = [
        migrations.CreateModel(
            name="BusinessObjective",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=140)),
                ("description", models.TextField(blank=True)),
                (
                    "metric",
                    models.CharField(
                        max_length=32,
                        choices=[
                            ("monthly_receipts", "Monthly cash receipts"),
                            ("monthly_cash_result", "Monthly net cash result"),
                            ("monthly_expenses", "Monthly expenses (maximum)"),
                            ("overdue_balance", "Overdue unpaid balance (maximum)"),
                            ("active_clients", "Active clients"),
                            ("cash_per_hour", "Collected cash per logged hour"),
                        ],
                    ),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("target", models.DecimalField(decimal_places=2, max_digits=18)),
                ("due_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("paused", "Paused"),
                            ("completed", "Completed"),
                        ],
                        default="active",
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["due_date", "id"],
                "indexes": [
                    models.Index(fields=["status", "due_date"], name="objective_status_due_idx")
                ],
            },
        ),
        migrations.CreateModel(
            name="BusinessStrategyDecision",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("title", models.CharField(max_length=160)),
                (
                    "kind",
                    models.CharField(
                        max_length=16,
                        choices=[
                            ("pricing", "Pricing and packaging"),
                            ("outreach", "Client outreach and pitching"),
                            ("delivery", "Delivery and scope control"),
                            ("collections", "Receivables and payment terms"),
                            ("costs", "Cost management"),
                            ("capacity", "Time and capacity"),
                            ("other", "Other"),
                        ],
                    ),
                ),
                ("rationale", models.TextField(blank=True)),
                ("expected_effect", models.CharField(max_length=280, blank=True)),
                (
                    "metric",
                    models.CharField(
                        max_length=32,
                        choices=[
                            ("monthly_receipts", "Monthly cash receipts"),
                            ("monthly_cash_result", "Monthly net cash result"),
                            ("monthly_expenses", "Monthly expenses (maximum)"),
                            ("overdue_balance", "Overdue unpaid balance (maximum)"),
                            ("active_clients", "Active clients"),
                            ("cash_per_hour", "Collected cash per logged hour"),
                        ],
                    ),
                ),
                ("currency", models.CharField(default="USD", max_length=3)),
                (
                    "baseline",
                    models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True),
                ),
                ("started_on", models.DateField()),
                ("review_on", models.DateField()),
                (
                    "status",
                    models.CharField(
                        max_length=12,
                        choices=[
                            ("planned", "Planned"),
                            ("active", "In progress"),
                            ("reviewed", "Reviewed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="planned",
                    ),
                ),
                ("outcome_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        to="ledger.client",
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="strategy_decisions",
                    ),
                ),
                (
                    "objective",
                    models.ForeignKey(
                        to="ledger.businessobjective",
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="decisions",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["status", "review_on"], name="strategy_status_review_idx"),
                    models.Index(fields=["kind", "started_on"], name="strategy_kind_start_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BusinessAdvisoryReport",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("provider", models.CharField(max_length=16)),
                ("model_name", models.CharField(max_length=100, blank=True)),
                ("evidence_signature", models.CharField(max_length=64)),
                ("advice", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["provider", "created_at"],
                        name="business_advice_provider_idx",
                    )
                ],
            },
        ),
    ]
