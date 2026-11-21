# Invoices and payments

Invoices support creation, editing of permitted fields and status filters. The payment endpoint is transactional, rejects non-positive and over-balance payments, allocates FIFO against scheduled instalments, updates invoice state, emits immutable audit events and recalculates the client score. Paid and partial statuses are controlled by payment records; written-off and disputed statuses are explicitly audited. New invoices are blocked for blacklisted clients and clients with a health score below 40.

## Changelog
- 2026-10-28: Added invoice lifecycle endpoints and payment recording workflow.
