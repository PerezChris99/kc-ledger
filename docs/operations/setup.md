# KC Ledger — local setup and database configuration

**Primary database: local PostgreSQL. SQLite is a deliberate offline fallback.** The React/JSX frontend, Django Ninja API and Windows desktop all use the same backend configuration.

## Source / local PostgreSQL

Run these commands from the repository root.

1. Install PostgreSQL 15+ and create an isolated `kc_ledger` database and login role; see [database runbook](postgresql-and-fallback.md).
2. Copy `.env.example` to `.env`. Supply real `DJANGO_SECRET_KEY`, owner credentials, and `LEDGER_DB_PASSWORD`; keep it out of Git.
3. For the Vite development server, include `http://127.0.0.1:5173` in the comma-separated `DJANGO_CSRF_TRUSTED_ORIGINS` setting before starting Django.
4. Use Python 3.12 and Node.js 22.

```bash
python -m pip install -e ".[dev]"
python backend/manage.py db_status
python backend/manage.py migrate
python backend/manage.py check_db_transition
python backend/manage.py ensure_owner
python backend/manage.py runserver 127.0.0.1:8000
```

The repository-root `.env` is loaded automatically for the Django source runtime without overwriting existing OS environment variables. `db_status` must report `postgresql`. In a second terminal, run `npm ci` then `npm run dev -- --host 127.0.0.1`; Vite serves <http://127.0.0.1:5173> and proxies `/api` to Django.

## Docker browser route

```bash
docker compose up --build -d
docker compose ps
docker compose exec api python manage.py db_status
```

Visit <http://127.0.0.1:8080>. The Compose stack provisions a separate **local PostgreSQL 15** service on an internal network with persistent `ledger_pgdata` storage, not an external DB. The browser remains bound to loopback. No DB port is published. Set `LEDGER_DB_PASSWORD` in `.env` before first launch. The older `ledger_data` volume remains available for backup and carefully controlled migration.

To seed **fictional** test data only: `docker compose exec api python manage.py seed_demo`. Never seed a real financial ledger.

## Windows desktop

Build using `desktop/build_windows.ps1` on Windows 10/11 x64 with Python 3.12, Node 22, Inno Setup 6. The installed application reads PostgreSQL credentials from `%LOCALAPPDATA%\KCLedger\.env`. The native process prefers PostgreSQL; SQLite is selected and **pinned** only when necessary and explicitly permitted, or if there is pre-existing SQLite data. The installer retains per-user financial data. See [desktop architecture](../architecture/desktop-app.md) and [database runbook](postgresql-and-fallback.md).

## Verification

```bash
python backend/manage.py db_status
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
pytest -q
ruff check backend
npm run verify:source
npm run lint
npm run build
```

Use `LEDGER_DB_ENGINE=sqlite` only for intentional fallback or isolated tests. Do not expect automatic PostgreSQL/SQLite synchronization. Backup before upgrades; never commit `.env`, database files, customer financial records, or passwords.

See [operations](production-readiness.md), [verification](verification-matrix.md) and [troubleshooting](troubleshooting.md).

_Updated 2026-11-15 for PostgreSQL-first operation._

## Owner operations

- **Payment correction.** Open the client dossier and select **Reverse payment** on the receipt. Supply the reason, then record the replacement on the correct invoice. The original receipt and correction remain in audit history. A reversed pre-plan payment reopens a separate balance on the schedule. The payment form reuses its submission key when retrying an unchanged entry in the same tab. API integrations should supply a stable UUID in `submission_key` for each intended receipt.
- **Opening and closing balances.** Enter the source records before reconciliation. Prepare an independent UTF-8 CSV with the header `invoice,currency,outstanding` and one row per open invoice, for example `INV-001,UGX,125000.00`. Run `python backend/manage.py reconcile_ledger statement.csv` against the intended database. Stop posting while comparing. A missing, unexpected or mismatched open balance returns a nonzero exit code. A header-only file checks that all balances are closed.
- **Recover owner access.** From a trusted host terminal, check the selected database with `db_status`, then run `python backend/manage.py changepassword OWNER_USERNAME`. With Compose use `docker compose exec api python manage.py changepassword OWNER_USERNAME`. For the installed Windows app, run its executable with `--recover-owner` from the owning Windows account and enter the existing owner username and a new password. Protect that operating-system account and its recovery credentials. Changing the password invalidates existing Django sessions.
- **Backup monitoring.** The local desktop and Compose schedulers check for a backup at startup and every 30 minutes. A verified snapshot is created when the last available copy is over 24 hours old. When configured, the secondary copy must also exist. Mount a protected independent destination and set `LEDGER_SECONDARY_BACKUP_DIR` to its writable path. A failed attempt records an owner notification. An external monitor should run `python backend/manage.py backup_status` and alert on a nonzero exit, including when the application is down. This command checks freshness and readability; a restore drill verifies recoverability.
- **Hosted databases.** Configure managed snapshots or schedule `python scripts/production_migrate.py --backup-only` on a trusted external runner with the direct PostgreSQL URL, Django secret, AWS identity, S3 destination, and KMS key described in the deployment runbook. Backup-only mode verifies the offsite copy and exits before migrations or owner setup. A serverless function's local filesystem is temporary. Test restoration into a separate database and run reconciliation there before switching traffic.
