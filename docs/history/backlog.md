# KC Ledger: verified status and release backlog

This page describes the **current** code after PR #8 (merged 2026-11-15). The 2026-10-28 backlog is superseded.

## Implemented in source and covered by existing CI

- React 18 frontend fully migrated to JavaScript/JSX; TypeScript source/configuration removed.
- KC navy/cyan/yellow/gold light-paper UI, client editing, guarded invoice editing, plan editing, editable work records, soft archive/restore, target edit/archive, reporting and insights.
- Django Ninja, SQLite WAL, persistent login throttle, CSRF, bounded input/query sizes and transactional financial operations.
- Multi-currency client scoring, FIFO allocations, late/at-risk/broken plan verdicts and scheduled reminders.
- ReportLab invoice and client dossier PDF exports, checked SQLite backup and guarded offline restore.
- Windows desktop host, PyInstaller bundling, Inno Setup build, WebView2 bootstrapper signature verification and native executable smoke route.
- Python/npm lockfiles, CI lint/unit/security, Docker health, Chromium E2E and Windows build jobs.

## Code-level follow-up in this hardening pass

- Revenue target accumulation changed to grouped SQL totals per invoice currency, with bounded FX lookups.
- Creation and replacement of time entries now enforce identical two-decimal hour precision.
- Regression tests added for both behaviors.
- JSX-only source verification included in frontend CI.

## External/operational acceptance still necessary

| Gate | Current evidence | Release requirement |
| --- | --- | --- |
| Build/install | Windows package built and executable self-test passed on hosted CI | Install, launch, update, relaunch, uninstall on clean Windows 10/11 x64 systems |
| UI/accessibility | Chromium route smoke and screenshots in CI | Modal keyboard/focus audit, reduced motion, high zoom and visual acceptance on real devices |
| Restore | Online backup and restore code/tests | Run operator restore drill using a disposable copy and verify amounts/scores |
| Recovery | Local backup available | Configure protected secondary/off-device backup and separately decide on encryption |
| FX provider | External fetch support exists | Configure valid exchangerate.host account/key and test live feed/limits, or use manual FX rates |
| Distribution | Installer artifact available from GitHub CI | Signing certificate, release version/tag, checksum, installer provenance and distribution instructions |
| Network security | Loopback service by default | Never expose without reviewed TLS, access and threat model |
| Commercial/legal | Proprietary LICENSE in repository | Confirm repository visibility, legal owner and intended distribution policy |

**Not blockers unless intentionally restored to scope:** the historical stock-photo carousel and the old dark-first design from the October concept. The current application uses owner login and the KC light-paper theme.

Do not mark any physical-machine gate as passed merely because the source or CI was successful. See [verification matrix](../operations/verification-matrix.md) and [release runbook](../operations/production-readiness.md).

_Updated 2026-11-15._
