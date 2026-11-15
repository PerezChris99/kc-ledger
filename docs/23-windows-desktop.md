# Windows desktop: build, install and recovery

**Status:** Windows package and self-test pass in GitHub Actions, but no signed/clean-device production release has been certified.

## Build requirements

Windows 10/11 x64, Python 3.12, Node.js 22, Inno Setup 6. Run in PowerShell from a fresh checkout:

```powershell
powershell -ExecutionPolicy Bypass -File desktop\build_windows.ps1
```

The script executes `npm ci`, ESLint and Vite production build; collects Django static files; installs the Python desktop extra; builds a PyInstaller one-folder executable; downloads and checks the Microsoft WebView2 bootstrapper Authenticode signature; then compiles an Inno Setup installer if `ISCC.exe` is present. The script prints SHA-256 hashes. A successful build alone is **not** an installer installation test.

## Produced files

- PyInstaller runtime: `dist\KC Ledger\KC Ledger.exe` and bundled dependencies.
- Inno Setup installer: `installer-output\KC-Ledger-Setup-0.1.0.exe` (when Inno Setup is installed).
- In GitHub CI, downloadable artifact: `kc-ledger-windows-output`; separate smoke-test JSON: `kc-ledger-windows-smoke`.

The app operates without separately installed Python/Node/Docker. WebView2 must be installed, or its signed Microsoft bootstrapper is invoked. That bootstrapper can require network access on first installation.

## Runtime storage and recovery

| File | Per-user location |
| --- | --- |
| Database | `%LOCALAPPDATA%\KCLedger\ledger.sqlite3` |
| Persistent Django signing key | `%LOCALAPPDATA%\KCLedger\.session-key` |
| Backups | `%LOCALAPPDATA%\KCLedger\backups` |
| Logs | `%LOCALAPPDATA%\KCLedger\kc-ledger.log` |

Never delete the per-user data directory as part of a routine upgrade. The installer is configured not to remove financial records on uninstall. Take and verify a backup **before** switching application versions, and use the dedicated restore management command only while the app is stopped.

## Release check

Verify clean Windows 10 and 11 installations, first-run account creation, WebView2 GUI use, invoices and PDFs, failed-login behavior, app shutdown/restart, migration from old data, integrity-checked restore, uninstall retention, offline launch and antivirus/SmartScreen behavior. Use an actual signed publisher build for public distribution; publish hashes, supported OS and recovery guidance.

See [production readiness](21-production-readiness.md) for the full runbook. All checked CI steps are described in [verification matrix](24-verification-matrix.md).

_Updated 2026-11-15; old TypeScript and WeasyPrint instructions removed._
