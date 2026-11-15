# KC Ledger API reference (implemented)

Base path: `/api/`. Authentication uses Django staff session cookies; unsafe requests require CSRF. `GET /api/health`, `GET /api/csrf`, `GET /api/session` and `POST /api/auth/login` bootstrap a session. `POST /api/auth/logout` ends it. Do not call this API from a different origin without an explicitly designed authentication and CSRF model.

| Route | Purpose |
| --- | --- |
| `GET /dashboard` | Live KPI totals, trends, attention items, ageing and concentration |
| `GET, POST /clients` | Paginated/searchable clients; create client |
| `GET, PATCH, DELETE /clients/{id}` | Dossier, update, soft archive |
| `GET, POST /invoices` | List/search invoices; create |
| `PATCH /invoices/{id}` | Guarded title/due-date/status/notes edits |
| `POST /payments` | Transactional payment with FIFO instalment allocation |
| `GET, POST /plans` | Instalment plans |
| `PATCH /plans/{invoice_id}` | Edit before allocated payments exist |
| `GET, POST /engagements` | List/create engagements |
| `PATCH, DELETE /engagements/{id}` | Edit/archive engagement |
| `GET, POST /time-entries` | List/create time entries |
| `PUT, DELETE /time-entries/{id}` | Replace/archive work hours |
| `GET, POST /expenses` | List/create expenses |
| `PUT, DELETE /expenses/{id}` | Replace/archive expense |
| `GET /archived-records` | List recently archived work records |
| `POST /archived-records/{kind}/{id}/restore` | Restore archived engagement, time entry or expense |
| `GET /insights` | Client economics, receivables and work records |
| `GET /avoid` | High-risk clients and score explanations |
| `GET /events` | Filterable append-only audit trail |
| `GET /calendar` | Invoice/instalment due dates |
| `GET /fx/convert` | Conversion using saved FX rates |
| `POST /fx/rates` | Set a manual FX rate |
| `GET, POST /targets` | List/create targets and live progress |
| `PATCH, DELETE /targets/{id}` | Edit/archive targets |
| `GET, PATCH /settings` | Settings, timezone, base currency and notification preferences |
| `GET /notifications` | Poll event-based notifications |
| `GET /clients/{id}/dossier.pdf` | Client risk dossier via ReportLab |
| `GET /invoices/{id}/pdf` | Invoice statement via ReportLab |

Each item above is relative to `/api`. User-friendly financial validation errors return 4xx responses; never infer success from HTTP 200 without checking the actual response.

**Rules:** currency fields use three-letter codes; API money uses decimal-precision values. A payment cannot exceed an outstanding invoice or unallocated instalment schedule balance. Paid and partial invoice status is payment-controlled, and a written-off invoice cannot be reopened by simply editing status. Work-hour creation and replacement both reject values with more than two decimal places.

Current implementation is in [backend/ledger/api.py](../backend/ledger/api.py) and [backend/ledger/api_extra.py](../backend/ledger/api_extra.py). Tests are in [backend/ledger/tests](../backend/ledger/tests).

_Updated 2026-11-15._
