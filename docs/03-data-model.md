# Data model

The Django ORM models represent clients, engagements, invoices, instalments, plan metadata, payments and allocations, expenses, append-only events, signal types, time entries, targets, FX rates and key/value metadata. Financial amounts use Decimal fields. Domain records use soft deletion; audit events are append-only. Foreign keys protect historical financial records from accidental cascaded deletion. Database constraints enforce positive monetary values and bounded client scores.

## Changelog
- 2026-10-28: Added core domain models and admin registrations.
