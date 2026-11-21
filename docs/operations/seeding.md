# Demo seeding

Run python manage.py seed_demo to create a repeatable fictional dataset. All demo client emails use the reserved example.test domain. The command creates six clients, engagements, invoices, payments, one instalment per invoice and representative risk events. It is for local validation only; it must never be mistaken for real financial data.

Run python manage.py reset_demo to soft-delete demo domain records. Append-only audit events are preserved, including demo event history.

## Changelog
- 2026-10-28: Documented seed and reset commands.
