# Windows desktop packaging and recovery

The source implements a Windows desktop host plus packaging scripts; this is
not yet a tested or signed release.

## Build requirements

Windows 10/11 x64, Python 3.12, Node.js 22, Inno Setup 6 and the committed
npm lockfile. On a Windows workstation, run:

    powershell -ExecutionPolicy Bypass -File desktop\build_windows.ps1

The script builds React, runs TypeScript checks, collects static files,
packages the desktop launcher with PyInstaller and builds an Inno Setup
per-user installer when ISCC.exe is available. It emits SHA256 hashes.

## Runtime

The installed application runs a local Django API inside a Waitress server
listening on 127.0.0.1 only, with a native WebView2 window. A Windows mutex
prevents multiple instances in the same session. The launcher checks API
health before opening the window and starts APScheduler once.

- Database: %LOCALAPPDATA%\KCLedger\ledger.sqlite3
- Session signing key: %LOCALAPPDATA%\KCLedger\.session-key
- Backups: %LOCALAPPDATA%\KCLedger\backups
- Logs: %LOCALAPPDATA%\KCLedger\kc-ledger.log

On a first launch, the owner creates a new private login with no default
credentials. Before migrating an existing database, a verified online backup
is created. ReportLab exports PDFs without GTK/Cairo libraries.

The per-user installer does not delete user financial records on uninstall.

## Required remaining validation

- Produce and commit npm/Python lockfiles and verify fresh-clone installs
- Verify Windows WebView2 detection and installation on a clean VM
- Run Windows 10/11 install, user journey, PDF, restart, crash and upgrade tests
- Sign the final installer with an externally provided certificate
- Record installer hashes and a release tag only after successful validation

The browser deployment remains available through Docker Compose.

## WebView2 installation prerequisite

The Windows build downloads Microsoft's evergreen WebView2 bootstrapper, verifies its Authenticode signature, and bundles it with Inno Setup. On machines without a registered WebView2 runtime, installation invokes the signed Microsoft bootstrapper. That step requires internet access on the first install; for completely offline distribution the large Microsoft standalone Evergreen installer must be substituted and verified separately. The packaged KC Ledger app still requires no separately installed Python or Node.js.
