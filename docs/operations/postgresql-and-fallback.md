# Local PostgreSQL first, SQLite fallback: KC Ledger database runbook

## Supported database modes

| Mode | Setting | Behavior |
| --- | --- | --- |
| **PostgreSQL (default)** | `LEDGER_DB_ENGINE=postgres` | Connect to the authoritative local PostgreSQL database; fail closed on errors |
| SQLite (explicit fallback) | `LEDGER_DB_ENGINE=sqlite` | Use the chosen SQLite file; **never** synchronizes with PostgreSQL |
| Auto (single-machine desktop) | `LEDGER_DB_ENGINE=auto`, `LEDGER_ALLOW_SQLITE_FALLBACK=1` | Prefer PostgreSQL, select SQLite only when PostgreSQL is offline during first selection; pin that backend permanently |

A pinned selection is stored in `LEDGER_DB_PIN_PATH` (normally beside SQLite). Once PostgreSQL is selected, its outages **do not** redirect writes into SQLite. Once SQLite is selected, PostgreSQL's return **does not** move records without an explicit migration. A pre-existing Django SQLite file is preserved and selected automatically in auto mode. Invalid PostgreSQL credentials, missing databases and authorization failures are errors, not fallback reasons.

**A database outage must not create two different financial histories.** A split database is worse than an explicit offline error.

## Local PostgreSQL installation (Windows/Linux source)

Install and start PostgreSQL (version **15 or newer**). Create a dedicated user and database from your local `psql` administrator session:

```sql
CREATE ROLE kc_ledger LOGIN;
\password kc_ledger
CREATE DATABASE kc_ledger OWNER kc_ledger ENCODING 'UTF8';
```

The `\password` command is interactive; do not put a production password in terminal history. The role should have access only to this ledger's database. Restrict PostgreSQL to the local machine with `listen_addresses = 'localhost'`, an appropriate `pg_hba.conf` password-authentication rule, and a firewall blocking external database access.

Copy `.env.example` to `.env` in the repository root and set:

```dotenv
DJANGO_SECRET_KEY=<unique secret, 40+ characters>
LEDGER_USERNAME=<your owner name>
LEDGER_PASSWORD=<unique owner password, at least 16 characters>
LEDGER_DB_ENGINE=postgres
LEDGER_DB_HOST=127.0.0.1
LEDGER_DB_PORT=5432
LEDGER_DB_NAME=kc_ledger
LEDGER_DB_USER=kc_ledger
LEDGER_DB_PASSWORD=<the PostgreSQL role password>
```

The backend now loads the repository-root `.env` automatically for local Python runs (without overriding real OS environment variables). `.env` is Git-ignored. Install Python 3.12 and dependencies:

```bash
python -m pip install -e ".[dev]"
python backend/manage.py db_status
python backend/manage.py migrate --noinput
python backend/manage.py check_db_transition
python backend/manage.py ensure_owner
python backend/manage.py runserver 127.0.0.1:8000
```

Run `npm ci && npm run dev` for the React frontend in a separate terminal. The `db_status` command runs `SELECT 1` and reports the active vendor; **it must say `postgresql`**. Django keeps PostgreSQL connections open for up to 60 seconds (`LEDGER_DB_CONN_MAX_AGE`), checks them before reuse, and applies 3-second connect and server-side statement timeouts. `/api/health` responds with 503 if the database is not usable.

## Docker browser runtime: isolated local PostgreSQL

`docker compose up --build -d` starts a PostgreSQL 15 container and the backend. Database files persist in the `ledger_pgdata` volume. No database port is published to the host or internet; Django connects to the internal Compose service `db:5432`. The app remains at <http://127.0.0.1:8080>.

```bash
docker compose ps
docker compose exec api python manage.py db_status
docker compose exec api python manage.py showmigrations ledger
docker compose exec api python manage.py backup_ledger
```

Set `LEDGER_DB_PASSWORD` to a strong value in `.env` **before first startup**; PostgreSQL initialization credentials in a populated volume are not changed merely by editing `.env`. Do **not** run `docker compose down -v` on a real ledger, as it destroys the persisted PostgreSQL volume.

The Docker runtime is intentionally configured as strict `postgres` mode rather than auto mode. If PostgreSQL fails, it stops serving requests instead of silently using another database.

To connect the **source Python process** directly to a PostgreSQL instance already installed on your Windows/Linux machine, use `LEDGER_DB_HOST=127.0.0.1` in `.env`; no Docker DB service is necessary. Docker's default separate local DB is an isolated container database, not your separately installed Windows PostgreSQL instance.

## Windows desktop

The native executable reads its owner-specific database settings from `%LOCALAPPDATA%\KCLedger\.env` (or existing OS environment variables). Put the PostgreSQL variables there, then launch KC Ledger. For a new installation, `auto` mode prefers the local PostgreSQL server when reachable. If unavailable and fallback is enabled, SQLite is used and the backend selection is pinned in `%LOCALAPPDATA%\KCLedger\.database-backend`.

Existing desktop SQLite data remains SQLite until **deliberately migrated**. To insist on PostgreSQL and disable fallback, set `LEDGER_DB_ENGINE=postgres` in that per-user `.env`. When PostgreSQL is the desktop backend, install matching `pg_dump` / `pg_restore` client tools or configure `LEDGER_PG_BIN` so pre-upgrade backups work.

## Migrating an existing SQLite ledger to PostgreSQL

**Do not simply change the database engine on a live or populated ledger.** This does not copy data, passwords, audit history or payments.

1. Stop all KC Ledger processes. Verify the existing SQLite database backup using `LEDGER_DB_ENGINE=sqlite python backend/manage.py backup_ledger` (in PowerShell, set the environment variable for the process before running the command).
2. With SQLite explicitly selected, export a **sensitive, temporary** Django JSON fixture on a secure drive. Example:
   `python backend/manage.py dumpdata --exclude contenttypes --exclude auth.permission --exclude sessions.session --natural-foreign --natural-primary --indent 2 --output ledger-migration.json`.
3. Configure a **new, empty PostgreSQL database**, switch to `LEDGER_DB_ENGINE=postgres`, run `python backend/manage.py migrate --noinput`, and load the fixture with `python backend/manage.py loaddata ledger-migration.json`. Do not import over an existing populated PostgreSQL ledger.
4. Reconcile **all tables and record counts**, including archived records, audit events, invoices, payments, allocations, owner credentials, and decimal totals. Confirm PDF export, scores, login, and management commands against the new database.
5. Only after successful reconciliation set `LEDGER_SQLITE_MIGRATION_VERIFIED=1` whenever the old SQLite file still exists, including Docker, source and desktop installations. `check_db_transition` refuses an unverified cutover. Retain the original snapshot in secure storage; destroy the temporary JSON fixture securely.
6. For desktop `auto` mode, after a verified migration **and while stopped**, intentionally set `LEDGER_DB_ENGINE=postgres`. Do not delete the pin or original SQLite until reconciliation is documented. The explicit engine override is a deliberate operator choice.

**No automated cross-engine synchronization is supported.** This migration is a one-time, offline, operator-controlled cutover. The database copies must never accept writes at the same time.

## Backup and recovery

`backup_ledger` uses SQLite's online backup API in SQLite mode, or `pg_dump --format=custom` in PostgreSQL mode. PostgreSQL archives are validated with `pg_restore --list`. Verified snapshots are written atomically and can be copied to `LEDGER_SECONDARY_BACKUP_DIR`. Both modes support bounded retention.

Dry-run verification:

```bash
python backend/manage.py backup_ledger
python backend/manage.py restore_ledger /path/to/ledger-YYYYMMDD-HHMMSS.dump
```

To **apply** a PostgreSQL restore, fully stop the app/scheduler first, ensure no other writers remain, then use `--apply --confirm RESTORE-LEDGER`. A safety `pg_dump` is taken first; `pg_restore` executes `--single-transaction --exit-on-error`. The PostgreSQL client tools must be installed (inside Docker they're included). Protect backup files; they are **not encrypted by the application**.

## Acceptance checklist

- [ ] `db_status` reports `postgresql` using the intended database and host
- [ ] `showmigrations` and `makemigrations --check --dry-run` pass
- [ ] Client → invoice → plan → payment flows persist after restart
- [ ] Transaction rollback, CSRF, login throttle and FX tests pass against PostgreSQL
- [ ] PostgreSQL stopped: strict mode returns an error, not silent SQLite writes
- [ ] SQLite fallback and pinning behave as documented on a fresh machine
- [ ] PostgreSQL backup archive validates and an **offline** restore drill succeeds
- [ ] Old SQLite data is preserved, migrated and reconciled before cutover
- [ ] Postgres access is limited to the local machine or internal Compose network

_Implemented database configuration must be tested against your own local service. CI proves the connection to a separate disposable PostgreSQL service, not access to the user's PC._
