# Production readiness audit

This document records source-level findings and validation gates for the private KC Ledger deployment. It distinguishes implemented changes from checks that require executing the application.

## Operating boundary

KC Ledger is a single-owner financial application. It should remain bound to localhost unless a separate remote-access security design is approved. SQLite in WAL mode is appropriate for this workload; do not add distributed infrastructure without a measured need.

## Source-level issues addressed

- Production settings reject a missing, placeholder, or short Django secret key. Tests and explicit development mode retain a test/development fallback.
- Session middleware no longer writes the session row on every read-only request.
- First-owner bootstrap validates the configured password against Django password validators.
- Docker publishes the UI only on 127.0.0.1:8080, not every network interface.
- Docker publishes the UI on the host loopback interface, so the Django admin and API are not exposed to the LAN by the default Compose configuration.
- nginx adds a same-origin Content Security Policy and security headers, disables server tokens, limits request body size, and restricts the login route to POST.
- Client scoring snapshots aggregate payments and expenses in SQL by client/currency rather than instantiating every payment and expense row in Python.
- The one-second clock update is isolated in its own React component so the workspace does not rerender every second.
- Client, invoice, and event pagination offsets are clamped to non-negative bounded values.

## Remaining security work

1. Replace process-local login throttling with a persistent, atomic throttle suitable for restarts and future multi-process operation.
2. Add explicit request-body and query-string length limits at the application layer, plus stricter validation for every currency, amount, date, and enum input.
3. Review all mutation endpoints for transaction boundaries, idempotency, and audit-event coverage.
4. Decide whether Django admin should be disabled entirely in the packaged desktop edition.
5. Add a desktop-specific origin/host policy and ensure the local listener binds only to 127.0.0.1.
6. Lock Python and npm dependency resolution and run dependency vulnerability reviews.
7. Verify backup encryption and an off-device backup destination. The current SQLite online backup command integrity-checks backups but does not encrypt them.

## Remaining performance work

1. Convert remaining full-table Python aggregations in Insights and target calculations to grouped SQL aggregates.
2. Eliminate per-invoice instalment queries in client scoring by loading a client's schedules in one query.
3. Add query-count and query-plan regression tests for dashboard, client dossier, insights, and scoring.
4. Measure frontend production bundle size and split chart-heavy routes if the initial bundle is too large.
5. Verify SQLite indexes against actual query plans and add indexes only where EXPLAIN QUERY PLAN shows a meaningful scan.
6. Keep a single web worker for SQLite and the in-process scheduler. If the process model changes, run scheduled jobs in one explicitly supervised process rather than one per web worker.

## Launch validation gates

These are not complete until executed on a real desktop and target deployment:

- pytest
- ruff check backend
- npm run lint
- npm run build
- Django deployment checks with production environment variables
- Login throttling, CSRF, session expiry, logout and inactive-user tests
- Invoice creation, payment allocation, partial payment, write-off, plan edit and audit-history tests
- PDF export tests with the production PDF runtime
- SQLite backup, restore into a clean data directory, and post-restore integrity check
- Desktop startup, shutdown, restart, offline operation, and data persistence
- Browser console and network inspection at desktop and mobile breakpoints

A source change is not proof that the runtime passes these gates.

## Change log

- 2026-11-01: Recorded production security, performance, and runtime validation findings.
