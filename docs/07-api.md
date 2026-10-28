# API reference

The API is rooted at `/api/`. Private endpoints require an active staff session and unsafe requests use CSRF protection. `GET /api/health`, `GET /api/csrf`, `GET /api/session` and `POST /api/auth/login` are public bootstrap routes; logout requires an authenticated session.

| Endpoint | Purpose |
|---|---|
| `GET /api/dashboard` | Single response with KPIs, trend, status, aging, health and attention data |
| `GET/POST /api/clients` | Search/paginate clients; create client |
| `GET/PATCH/DELETE /api/clients/{id}` | Client dossier, update or soft archive |
| `GET/POST /api/invoices` | Search/paginate or create invoices |
| `PATCH /api/invoices/{id}` | Edit permitted invoice fields |
| `POST /api/payments` | Transactional payment record and FIFO allocation |
| `GET/POST /api/plans` | List plans or create an instalment schedule |
| `PATCH /api/plans/{invoice_id}` | Revise a schedule only before any payments are allocated; previous rows remain soft-deleted |
| `GET /api/avoid` | Low-score and blacklisted client dossiers |
| `GET /api/insights` | Receivables aging and revenue concentration |
| `GET /api/events` | Filterable audit history |
| `GET /api/calendar` | Invoice and instalment dates for a month |
| `GET /api/fx/convert` | Convert using stored direct/inverse rates |
| `POST /api/fx/rates` | Manually override an FX pair |
| `GET/POST /api/targets` | List or create financial targets |
| `GET/PATCH /api/settings` | Read/update base currency, timezone and notification preferences |
| `GET /api/notifications` | Poll recent event notifications |
| `GET /api/clients/{id}/dossier.pdf` | Download a client score and risk dossier |
| `GET /api/invoices/{id}/pdf` | Download an invoice statement and payment history |

Validation errors return a structured HTTP error. Financial amounts are Decimal values in the backend; the frontend formats them for display. Paid and partial invoice statuses are controlled by the payment workflow, not set directly through the invoice edit endpoint.

## Changelog
- 2026-10-28: Documented the implemented endpoint surface.
