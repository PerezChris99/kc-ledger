# KC Ledger: installation and local development

**Current runtime:** React 18 + JavaScript/JSX + Vite 8, Django 5.2 + Ninja, SQLite WAL. Choose either the local Docker browser application or the packaged Windows desktop application; they are independent installation routes.

## Docker browser route

Requirements: Docker Desktop / Docker Compose. Copy `.env.example` to `.env` and configure a **unique** `DJANGO_SECRET_KEY` (at least 40 characters), `LEDGER_USERNAME`, and `LEDGER_PASSWORD` (at least 16 characters). Keep `.env` out of Git.

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f api
```

Open <http://127.0.0.1:8080>. The public host binding is loopback-only by design. The owner bootstrap happens only on the first run; environment changes do not reset an existing password. Persistent application data resides in the `ledger_data` Docker volume.

To load **fictional test data only**: `docker compose exec api python manage.py seed_demo`.

## Source development route

Use Python 3.12 and Node.js 22. In a Python virtual environment install `python -m pip install -e ".[dev]"`, configure `DJANGO_SECRET_KEY`, and run:

```bash
python backend/manage.py check
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8000
```

In another terminal run `npm ci` followed by `npm run dev`. Open <http://127.0.0.1:5173>. Vite proxies `/api` to Django. Run `npm run lint`, `npm run build`, and `pytest -q` before committing.

## Windows desktop route

The source Windows builder is `desktop/build_windows.ps1`. Build on Windows 10/11 x64 with Python 3.12, Node.js 22 and Inno Setup 6; see [Windows packaging](23-windows-desktop.md). The installed app does not require separately installed Python, Node.js, Docker, or a running Vite server. It keeps data in `%LOCALAPPDATA%\KCLedger`.

## Boundaries

Do not publish the default localhost service to the LAN or internet. The PWA caches UI assets, **not financial API data**; it cannot write new financial records while disconnected. Back up before upgrades. Never commit actual client financial records, `.env`, desktop signing keys, generated databases, or production secrets.

See [operations and verification](21-production-readiness.md), [architecture](02-architecture.md) and [troubleshooting](20-troubleshooting.md).

_Updated 2026-11-15 to match the merged JSX and Windows desktop overhaul._
