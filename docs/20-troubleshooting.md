# Troubleshooting and recovery

## Verify your local PostgreSQL connection

```bash
python backend/manage.py db_status
python backend/manage.py showmigrations ledger
python backend/manage.py check
```

The first command must show `postgresql` for the primary database. Verify PostgreSQL is running, accepting TCP connections on `127.0.0.1:5432`, the role can log in, and `kc_ledger` exists. Local Python loads repository-root `.env`; Docker uses its internal `db` hostname and separate PostgreSQL volume. Avoid conflating the two servers. Test a direct connection with `psql -h 127.0.0.1 -U kc_ledger -d kc_ledger -c "SELECT 1;"`.

## PostgreSQL unreachable / HTTP 503

Strict `postgres` mode **never writes into SQLite** if PostgreSQL goes offline. Restore PostgreSQL availability or use deliberate offline recovery with a verified migration. A 503 from `/api/health` means the configured database could not answer a live probe. Check PostgreSQL logs, credentials, user privileges, `pg_hba.conf` and firewall rules.

## SQLite fallback is still active

An `auto` installation pins its first successful backend in `.ledger-db-backend` (desktop: `%LOCALAPPDATA%\KCLedger\.database-backend`). This is expected: reconnecting PostgreSQL must not hide SQLite writes. Do **not** delete that file or change databases while live without first migrating and reconciling data. Legacy SQLite databases are preserved.

## PostgreSQL cutover blocked due to old SQLite

The `check_db_transition` command refuses to start a fresh PostgreSQL app if the old SQLite volume contains accounts or financial data. Back up the SQLite file, migrate data offline to PostgreSQL, compare every relevant table and all balances, then explicitly mark migration verified. See [migration runbook](25-postgresql-and-fallback.md).

## Backups

`python backend/manage.py backup_ledger` writes a verified `.dump` archive from PostgreSQL or `.sqlite3` online snapshot from SQLite, depending on the active backend. PostgreSQL backup/restore requires matching `pg_dump/pg_restore` client tools. Install the tools or set `LEDGER_PG_BIN` to the directory containing them. For recovery, stop the app/scheduler first; run `restore_ledger <archive>` to validate, then use `--apply --confirm RESTORE-LEDGER` after confirming target and safety backup. Never restore an archive to the wrong database.

## Windows desktop

The native app reads its per-user PostgreSQL configuration from `%LOCALAPPDATA%\KCLedger\.env`. An existing `ledger.sqlite3` is not automatically copied. For PostgreSQL-mode upgrades, backup client utilities must be available locally. Review `%LOCALAPPDATA%\KCLedger\kc-ledger.log`.

## PWA and login

The PWA caches static assets, never authoritative API financial responses. Financial writes require a live backend. A login failure may be due to bad credentials, persistent throttle, cookies/CSRF or the selected database containing another owner account. Do not disable CSRF or wipe the database to solve login issues.

_Updated 2026-11-15._
