# Windows desktop build, PostgreSQL and recovery

Build Windows 10/11 x64 installers using Python 3.12, Node.js 22 and Inno Setup 6:

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build_windows.ps1
```

The builder verifies JSX frontend lint/Vite, bundles Django/ReportLab/psycopg with PyInstaller, includes WebView2 bootstrapper after Microsoft signature verification, and builds Inno Setup output under `installer-output/`. During packaging and `--self-test`, SQLite is deliberately used in an isolated temporary database so a PostgreSQL service is not a build dependency.

At real launch, `%LOCALAPPDATA%\KCLedger\.env` configures the preferred local PostgreSQL server. In its absence, `auto` mode chooses a **pinned SQLite fallback** on a fresh install, preserving the previous native experience. Already populated SQLite installations are not silently switched. To use PostgreSQL, create the local role/database and configure the values in [database runbook](postgresql-and-fallback.md).

The installer preserves user data across upgrades/uninstall. PostgreSQL mode requires working `pg_dump` and `pg_restore` binaries for safety backups. Use `LEDGER_PG_BIN` to point at the PostgreSQL `bin` directory when they aren't on PATH.

The CI build/self-test checks packaged API/financial mutations/PDF/SQLite persistence. Actual interactive GUI use, PostgreSQL local-machine connectivity, code signing, clean-machine WebView2 setup and recovery drills require separate acceptance.

_Updated 2026-11-15._
