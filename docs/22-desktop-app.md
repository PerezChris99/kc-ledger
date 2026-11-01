# Desktop application architecture

KC Ledger remains a Django application. The desktop edition is a local shell around the existing React frontend and Django API; it does not replace the backend or duplicate financial rules.

## Recommended design

Use a lightweight native WebView host (pywebview) with a bundled Python runtime and Waitress serving the existing Django WSGI application.

On launch the desktop host:

1. Resolves a per-user application-data directory (for example, %LOCALAPPDATA%/KC Ledger on Windows).
2. Loads a persistent application secret and points LEDGER_DB_PATH at the per-user SQLite database.
3. Runs Django migrations and validates the owner account before opening the UI.
4. Starts exactly one Waitress server bound to 127.0.0.1 on an ephemeral local port.
5. Opens the React production build in a native WebView window at that local origin.
6. Starts APScheduler exactly once in the host process.
7. Stops the scheduler and HTTP server cleanly when the desktop window closes.

The frontend calls same-origin /api routes. No public API, cloud database, Docker daemon, Node.js runtime, or separate browser window is needed during normal use.

## Why this keeps Django

Django remains responsible for authentication, CSRF, financial validation, business logic, migrations, SQLite transactions, scoring, audit events, and PDF exports. The desktop layer only owns lifecycle, windowing, and per-user paths.

## Runtime footprint strategy

- One Python process and one embedded WebView; no nginx container, frontend dev server, Gunicorn master/worker tree, or Docker daemon.
- Use a production Vite build; never run Vite dev server in the installed app.
- Bind the HTTP listener to loopback only and use a random available port.
- Keep SQLite WAL, foreign keys, a finite busy timeout, and one writer process.
- Start scheduled jobs once; do not attach a scheduler to each request worker.
- Avoid polling the entire database when no desktop window is active.
- Store the database, backups, and persistent secret outside the installation directory so app updates do not overwrite user data.

## Packaging and platform notes

Build a separate signed installer per operating system. On Windows, pywebview uses the system WebView2 runtime; the installer should detect it and guide installation if missing. The packaged application must include Python dependencies, Django migrations, PDF templates, collected static files, and the React build.

The current PDF implementation uses WeasyPrint, which has native system-library requirements on Windows. A distributable installer must either bundle and verify those native libraries or replace the PDF renderer with a portable implementation before claiming a self-contained Windows package.

## First-run onboarding

The installed app must provide secure first-run owner setup. It must not ship a default username/password or rely on developers manually editing an .env file. The initial password must be validated with Django password validators and never written to logs.

## Security boundary

- Localhost-only listener; never bind to 0.0.0.0.
- Restrict allowed hosts to localhost and 127.0.0.1.
- Keep Django session authentication and CSRF protection.
- Do not expose Django admin in the desktop edition unless explicitly required.
- Do not enable remote debugging or WebView developer tools in release builds.
- Store secrets and SQLite data in the current OS user's application-data directory with OS-level access controls.
- Do not accept arbitrary URLs or external navigation in the native window.

## Release gate

The desktop edition is not complete until startup, shutdown, forced termination recovery, database persistence, migrations, PDF export, backup/restore, offline behavior, and memory/CPU use have been tested on the target OS.

## Change log

- 2026-11-01: Defined the recommended desktop architecture and packaging/security requirements.
