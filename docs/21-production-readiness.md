# KC Ledger — production and database release gates

**New default:** PostgreSQL 15+ as the local authoritative database, with SQLite WAL as a controlled and pinned fallback. Normal Docker/source deployments fail closed instead of allowing silent cross-database financial divergence. The original SQLite-only documentation is superseded.

## Security

- Bind Django/Waitress to local addresses only; Docker PostgreSQL 5432 is internal and not host-published.
- Use an isolated PostgreSQL role, strong private credentials and localhost authentication rules. Never commit `.env`.
- Django staff sessions, CSRF, rate limits and transactional financial mutations remain enforced.
- PostgreSQL uses persistent, health-checked connections. `/api/health` verifies an actual database query and returns 503 when unavailable.
- All financial records and audit history must be backed up; PostgreSQL `pg_dump` snapshots are **not encrypted** by the application.

## Developer verification

```bash
python -m pip install -e ".[dev]"
python backend/manage.py db_status
python backend/manage.py check --database default
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py migrate --plan
pytest -q
ruff check backend
ruff format --check backend
npm ci
npm run verify:source
npm run lint
npm run build
npm audit --audit-level=high
```

CI has independent SQLite and PostgreSQL backend jobs, a PostgreSQL service/backup check, Docker startup with PostgreSQL, Chromium browser financial flows and the Windows packaged application self-test. **CI must be rechecked for the specific new merge commit**; do not reuse an older green build as evidence.

## Real deployment acceptance

1. Create a dedicated PostgreSQL role/database on your actual local machine and verify `db_status` says `postgresql`.
2. Apply migrations against a clean DB and a **copy** of a populated older DB; reconcile schema/indexes/constraints.
3. Create client → engagement → invoice → instalment plan → partial/final payment and verify recorded sums, statuses and audit.
4. Kill/restart PostgreSQL and verify **no silent SQLite failover**, HTTP 503 and successful reconnection after service recovery.
5. If using automatic fallback in the desktop, exercise the pin behavior and prevent switching to a different financial history.
6. Make a verified PostgreSQL `pg_dump` snapshot and perform an offline restore drill into a disposable DB; compare exact amounts and record counts.
7. For existing SQLite data, complete a backed-up, **offline** verified migration before changing the database engine.
8. Test actual desktop installation, first-run owner setup, restart/upgrade, PDF, WebView2, offline behavior, accessibility and release signing.
9. Configure protected secondary/off-device backups, retention, filesystem access and encryption outside the application.

Do not expose this locally designed app to the public internet without a separately reviewed TLS and access model. Do not infer a 100% correct database connection to a user's PC from a hosted CI PostgreSQL service.

See [PostgreSQL & fallback runbook](25-postgresql-and-fallback.md), [verification matrix](24-verification-matrix.md), and [Windows packaging](23-windows-desktop.md).

_Updated 2026-11-15._
