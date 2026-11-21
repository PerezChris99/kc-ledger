"""Persist reproducible client intelligence and reviewable cross-client matches."""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("ledger", "0004_login_throttle")]

    operations = [
        migrations.CreateModel(
            name="ClientIntelligenceProfile",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("signals", models.JSONField(default=dict)),
                ("metrics", models.JSONField(default=dict)),
                ("sample_size", models.PositiveIntegerField(default=0)),
                ("score_snapshot", models.PositiveSmallIntegerField(default=50)),
                ("assessed_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intelligence_profile",
                        to="ledger.client",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ClientPatternAlert",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("signature", models.CharField(max_length=64)),
                ("overlap", models.JSONField(default=list)),
                ("similarity", models.PositiveSmallIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        max_length=12,
                        default="open",
                        choices=[
                            ("open", "Open"),
                            ("reviewed", "Reviewed"),
                            ("dismissed", "Dismissed"),
                            ("resolved", "Resolved"),
                        ],
                    ),
                ),
                ("review_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pattern_alerts",
                        to="ledger.client",
                    ),
                ),
                (
                    "reference_client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="historical_matches",
                        to="ledger.client",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["client", "status"], name="pattern_client_status_idx")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["client", "reference_client"], name="unique_pattern_client_pair"
                    ),
                    models.CheckConstraint(
                        condition=Q(similarity__gte=0, similarity__lte=100),
                        name="pattern_similarity_0_100",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ClientIntelligenceObservation",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("observed_on", models.DateField()),
                ("score", models.PositiveSmallIntegerField()),
                ("risk_index", models.PositiveSmallIntegerField()),
                ("evidence_count", models.PositiveIntegerField(default=0)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="intelligence_history",
                        to="ledger.client",
                    ),
                ),
            ],
            options={
                "ordering": ["-observed_on"],
                "indexes": [models.Index(fields=["observed_on"], name="intel_observed_day_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["client", "observed_on"], name="unique_client_intel_day"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ClientAdvisoryReport",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("provider", models.CharField(max_length=16)),
                ("model_name", models.CharField(max_length=100, blank=True)),
                ("advice", models.JSONField(default=dict)),
                ("evidence_signature", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="advisory_reports",
                        to="ledger.client",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["client", "created_at"], name="advice_client_created_idx")
                ],
            },
        ),
    ]
