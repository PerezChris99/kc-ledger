# Troubleshooting and recovery

## SQLite locked
The connection uses a 20-second busy timeout, WAL mode, foreign keys and NORMAL synchronous mode. Avoid copying the live database file while writes are in progress. Use python manage.py backup_ledger to create a consistent backup through SQLite's online backup API.

## Migrations
Back up the database before schema changes. Review python manage.py showmigrations and python manage.py migrate --plan before applying migrations. Do not delete migration history or use syncdb on an established production database.

## Stale PWA assets
The service worker caches only the application shell and static assets, never API responses. Close and reopen the installed app after a release; if assets remain stale, unregister the service worker from browser developer tools and reload.

## Authentication
Verify LEDGER_USERNAME, LEDGER_PASSWORD and DJANGO_SECRET_KEY in the private environment file. The initial owner password is not reset automatically on restart. Use HTTPS and set COOKIE_SECURE=1 behind a TLS-terminating reverse proxy.

## Changelog
- 2026-10-28: Added backup, migration and PWA troubleshooting notes.
