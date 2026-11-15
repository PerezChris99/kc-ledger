# Troubleshooting, maintenance and recovery

## GitHub still lists TypeScript

The merged default branch has no `.ts` or `.tsx` files. After PR #8 GitHub Linguist may display stale language statistics until repository indexing refreshes. Confirm `main` HEAD, inspect the tree, and run `npm run verify:source` on a fresh clone; do not rewrite working JSX to influence the statistics.

## Backend starts but frontend cannot reach it

For Docker use `docker compose ps`, `docker compose logs -f api`, and visit <http://127.0.0.1:8080/health>. For source mode verify `DJANGO_SECRET_KEY` and run `python backend/manage.py check`; the development API must listen on `127.0.0.1:8000`. Vite proxies `/api` there. Do not expose Django's development server publicly.

## Login or CSRF errors

Use the actual configured owner account; no default desktop login is shipped. The first Docker owner is created once, from `LEDGER_USERNAME` and `LEDGER_PASSWORD`. Verify cookie and CSRF responses and the nginx Host header when using the Docker route. A repeated-failure throttle persists in SQLite across restarts. Do not disable CSRF to solve a reverse-proxy issue.

## SQLite lock or migration issue

Keep one intended writer/scheduler process and let WAL/SQLite apply its busy timeout. Do not manually copy a live `ledger.sqlite3` as a consistent backup. Run `python backend/manage.py backup_ledger` instead. Before a version upgrade run `python backend/manage.py showmigrations` and `python backend/manage.py migrate --plan`; take a verified backup, then migrate. Never delete production migration files.

## Recovering financial data

**Stop all KC Ledger processes before applying restore.** Validate first:

```bash
python backend/manage.py restore_ledger /path/to/backup.sqlite3
```

Apply only when you have checked the target and retained a second copy:

```bash
python backend/manage.py restore_ledger /path/to/backup.sqlite3 --apply --confirm RESTORE-LEDGER
```

Restore code creates a pre-restore safety backup and verifies database integrity. The backup is **not encrypted automatically**; protect copies and test the complete recovery workflow before relying on it.

## Stale PWA assets

PWA caches static UI assets, not live ledger API responses. After updating, close/reopen the app, then clear the browser service worker/cache if needed. Offline access to cached UI is not a substitute for offline transaction support.

## Windows installer/WebView2

Build with Python 3.12, Node 22 and Inno Setup 6. The installer includes Microsoft's signed WebView2 bootstrapper but may need internet to fetch WebView2 on first installation. Windows runtime data lives in `%LOCALAPPDATA%\KCLedger`. The installer should not erase this directory on uninstall.

See [Windows packaging](23-windows-desktop.md), [release checklist](21-production-readiness.md), and [test matrix](24-verification-matrix.md).

_Updated 2026-11-15._
