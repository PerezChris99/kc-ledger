from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ledger", "0003_recurring_retainer_fields")]

    operations = [
        migrations.CreateModel(
            name="LoginThrottle",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("window_started_at", models.DateTimeField()),
                ("locked_until", models.DateTimeField(null=True, blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
