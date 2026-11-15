# KC Ledger — local setup and database configuration

**Primary database: local PostgreSQL. SQLite is a deliberate offline fallback.** The React/JSX frontend, Django Ninja API and Windows desktop all use the same backend configuration.

## Source / local PostgreSQL

1. Install PostgreSQL 15+ and create an isolated `kc_ledger` database and login role; see [database runbook](25-postgresql-and-fallback.md).
2. Copy `.env.example` to `.env`. Supply real `DJANGO_SECRET_KEY`, owner credentials, and `LEDGER_DB_PASSWORD`; keep it out of Git.
3. Use Python 3.12 and Node.js 22.

```bash
python -m pip install -e ".[dev]"
python backend/manage.py db_status
python backend/manage.py migrate
python backend/manage.py check_db_transition
python backend/manage.py ensure_owner
python backend/manage.py runserver 127.0.0.1:8000
```

The repository-root `.env` is loaded automatically for the Django source runtime without overwriting existing OS environment variables. `db_status` must report `postgresql`. In a second terminal, run `npm ci` then `npm run dev`; Vite serves <http://127.0.0.1:5173> and proxies `/api` to Django.

## Docker browser route

```bash
docker compose up --build -d
docker compose ps
docker compose exec api python manage.py db_status
```

Visit <http://127.0.0.1:8080>. The Compose stack provisions a separate **local PostgreSQL 15** service on an internal network with persistent `ledger_pgdata` storage, not an external DB. The browser remains bound to loopback. No DB port is published. Set `LEDGER_DB_PASSWORD` in `.env` before first launch. The older `ledger_data` volume remains available for backup and carefully controlled migration.

To seed **fictional** test data only: `docker compose exec api python manage.py seed_demo`. Never seed a real financial ledger.

## Windows desktop

Build using `desktop/build_windows.ps1` on Windows 10/11 x64 with Python 3.12, Node 22, Inno Setup 6. The installed application reads PostgreSQL credentials from `%LOCALAPPDATA%\KCLedger\.env`. The native process prefers PostgreSQL; SQLite is selected and **pinned** only when necessary and explicitly permitted, or if there is pre-existing SQLite data. The installer retains per-user financial data. See [desktop architecture](22-desktop-app.md) and [database runbook](25-postgresql-and-fallback.md).

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

See [operations](21-production-readiness.md), [verification](24-verification-matrix.md) and [troubleshooting](20-troubleshooting.md).

_Updated 2026-11-15 for PostgreSQL-first operation._
