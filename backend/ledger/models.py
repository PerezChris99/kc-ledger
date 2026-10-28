from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class LiveQuerySet(models.QuerySet):
    def delete(self):
        from django.utils import timezone
        count = self.update(deleted_at=timezone.now(), updated_at=timezone.now())
        return count, {self.model._meta.label: count}

    def hard_delete(self):
        return super().delete()


class LiveManager(models.Manager.from_queryset(LiveQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    objects = LiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def delete(self, using=None, keep_parents=False):
        self.soft_delete()
        return 1, {self._meta.label: 1}


class Client(SoftDeleteModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ARCHIVED = "archived", "Archived"
        BLACKLISTED = "blacklisted", "Blacklisted"

    name = models.CharField(max_length=160, db_index=True)
    company = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    source = models.CharField(max_length=120, blank=True)
    referred_by = models.CharField(max_length=160, blank=True)
    rate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    rate_unit = models.CharField(max_length=16, default="hour")
    started_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    score = models.PositiveSmallIntegerField(default=50)
    score_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status", "name"], name="client_status_name_idx"), models.Index(fields=["score", "status"], name="client_score_status_idx")]
        constraints = [models.CheckConstraint(condition=Q(score__gte=0, score__lte=100), name="client_score_0_100")]

    def __str__(self):
        return self.name


class Engagement(SoftDeleteModel):
    class Kind(models.TextChoices):
        FIXED = "fixed", "Fixed"
        HOURLY = "hourly", "Hourly"
        RETAINER = "retainer", "Retainer"
        MILESTONE = "milestone", "Milestone"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"
        PAUSED = "paused", "Paused"

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="engagements")
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.FIXED)
    agreed_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    rate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    scope_notes = models.TextField(blank=True)
    sow_deliverables = models.JSONField(default=list, blank=True)
    revision_limit = models.PositiveIntegerField(default=0)
    revisions_used = models.PositiveIntegerField(default=0)
    recurring_interval_days = models.PositiveSmallIntegerField(default=0)
    next_invoice_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["client", "status"], name="engagement_client_status_idx")]

    def __str__(self):
        return f"{self.client.name} — {self.name}"


class Invoice(SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"
        WRITTEN_OFF = "written_off", "Written off"
        DISPUTED = "disputed", "Disputed"

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    engagement = models.ForeignKey(Engagement, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    number = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=200)
    issue_date = models.DateField()
    due_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issue_date", "-id"]
        indexes = [models.Index(fields=["client", "status"], name="invoice_client_status_idx"), models.Index(fields=["status", "due_date"], name="invoice_status_due_idx")]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="invoice_amount_positive")]

    def __str__(self):
        return self.number


class PlanMeta(SoftDeleteModel):
    invoice = models.OneToOneField(Invoice, primary_key=True, on_delete=models.CASCADE, related_name="plan_meta")
    plan_deadline = models.DateField(null=True, blank=True)
    last_verdict = models.CharField(max_length=16, blank=True)
    notes = models.TextField(blank=True)


class Instalment(SoftDeleteModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        LATE = "late", "Late"
        OVERDUE = "overdue", "Overdue"
        WAIVED = "waived", "Waived"
        MISSED = "missed", "Missed"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="instalments")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="instalments")
    seq = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField(db_index=True)
    grace_days = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    paid_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["seq"]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "seq"], condition=Q(deleted_at__isnull=True), name="unique_live_instalment_seq"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="instalment_amount_positive"),
        ]
        indexes = [models.Index(fields=["status", "due_date"], name="instalment_status_due_idx")]

    def __str__(self):
        return f"{self.invoice.number} / {self.seq} — {self.label}"


class Payment(SoftDeleteModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    paid_on = models.DateField(db_index=True)
    method = models.CharField(max_length=40, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-paid_on", "-id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive")]
        indexes = [models.Index(fields=["client", "paid_on"], name="payment_client_paid_idx")]

    def __str__(self):
        return f"{self.invoice.number} payment {self.pk}"


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    instalment = models.ForeignKey(Instalment, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["payment", "instalment"], name="unique_payment_instalment_allocation"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="allocation_amount_positive"),
        ]


class Expense(SoftDeleteModel):
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses")
    engagement = models.ForeignKey(Engagement, null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses")
    category = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    spent_on = models.DateField(db_index=True)
    billable = models.BooleanField(default=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-spent_on"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive")]


class Event(models.Model):
    class Category(models.TextChoices):
        MONEY = "money", "Money"
        BEHAVIOUR = "behaviour", "Behaviour"
        COMMS = "comms", "Communications"
        DELIVERY = "delivery", "Delivery"
        RELATIONSHIP = "relationship", "Relationship"

    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT, related_name="events")
    engagement = models.ForeignKey(Engagement, null=True, blank=True, on_delete=models.PROTECT, related_name="events")
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.PROTECT, related_name="events")
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=80, db_index=True)
    category = models.CharField(max_length=16, choices=Category.choices)
    polarity = models.SmallIntegerField(default=0)
    weight = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("1"))
    title = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [models.Index(fields=["client", "occurred_at"], name="event_client_occurred_idx"), models.Index(fields=["category", "occurred_at"], name="event_category_occurred_idx")]
        constraints = [models.CheckConstraint(condition=Q(polarity__gte=-1, polarity__lte=1), name="event_polarity_range")]

    def save(self, *args, **kwargs):
        if self.pk and Event.objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit events are append-only and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events cannot be physically deleted.")


class SignalType(models.Model):
    kind = models.CharField(max_length=80, primary_key=True)
    label = models.CharField(max_length=120)
    category = models.CharField(max_length=16, choices=Event.Category.choices)
    polarity = models.SmallIntegerField(default=0)
    weight = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("1"))
    icon = models.CharField(max_length=80, blank=True)


class TimeEntry(SoftDeleteModel):
    class Category(models.TextChoices):
        BILLABLE = "billable", "Billable"
        REVISION = "revision", "Revision"
        ADMIN = "admin", "Admin"
        MEETING = "meeting", "Meeting"

    engagement = models.ForeignKey(Engagement, on_delete=models.PROTECT, related_name="time_entries")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="time_entries")
    hours = models.DecimalField(max_digits=8, decimal_places=2)
    category = models.CharField(max_length=16, choices=Category.choices)
    started_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(hours__gt=0), name="time_entry_hours_positive")]


class Target(SoftDeleteModel):
    class Type(models.TextChoices):
        REVENUE = "revenue", "Revenue"
        CLIENTS = "clients", "Clients"
        HOURS = "hours", "Hours"

    name = models.CharField(max_length=120)
    type = models.CharField(max_length=16, choices=Type.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    deadline = models.DateField()

    class Meta:
        ordering = ["deadline"]


class FxRate(models.Model):
    base = models.CharField(max_length=3)
    quote = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=8)
    fetched_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["base", "quote"], name="unique_fx_pair")]
        indexes = [models.Index(fields=["base", "quote", "fetched_at"], name="fx_pair_fetched_idx")]


class Meta(models.Model):
    key = models.CharField(max_length=120, primary_key=True)
    value = models.TextField()
