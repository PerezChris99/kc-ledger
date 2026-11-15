# Production readiness and release runbook

## Status as of 2026-11-15

The latest merged `main` commit `df094e3e4696e4da30742725f062adb1ce4937c1` passed the existing five-job GitHub CI suite: Django tests/Ruff/Python advisory scan; JS/JSX lint/Vite build/npm audit; Docker build and health; Chromium browser E2E; Windows executable/installer build and packaged backend smoke.

**Important:** a green CI run means that *those checks* passed, not that every possible financial edge case, keyboard interaction or clean-device installation has been exercised. Any later commit needs a fresh run; do not reuse these results as its verification.

## Threat model and safety boundaries

KC Ledger is single-owner financial software. Restrict access to one trusted operator and the loopback interface. The Docker frontend binds to `127.0.0.1:8080`. The desktop Waitress server binds to a random `127.0.0.1` port. The client cannot bypass Django's validation; state changes require staff session credentials and CSRF protection. The persistent login throttle resists restart resets. Audit events are append-only. Data at rest is **not encrypted by the application** and must be protected using operating-system account security and backup policy.

Do not publish an HTTP-only deployment to the public internet. A remotely accessible deployment requires a separately designed authentication, TLS and reverse-proxy security model and additional penetration checks.

## Developer verification before merge

```bash
python -m pip install -e ".[dev]"
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py migrate --plan
pytest -q
ruff check backend
ruff format --check backend
npm ci
npm run verify:source
npm run lint
npm run build
npm audit --audit-level=high
```

Run browser E2E against an **isolated test** instance with `npx playwright test`. Never run seeded tests against real financial data. CI additionally launches Docker and runs the Windows builder and packaged executable self-test.

## Financial acceptance scenarios

- Create/edit client; archive and verify unchanged retained history.
- Create invoice, record partial and final payments, prevent overpayment, verify outstanding balances and statuses.
- Create a multi-instalment plan, allocate FIFO, observe verdicts and reject edits after payment allocation.
- Test disputed, written-off, paid and partially paid invoice transitions, including forbidden updates and correct receivables.
- Add/edit/archive/restore engagements, time entries and expenses; confirm live analytics and client-scoring refresh.
- Verify currency conversion, known missing FX rates, manually stored rates and target projections.
- Generate invoice and dossier PDF with real representative data and validate totals.
- Verify authentication, CSRF, logout/session expiry, throttle and failed login behavior.

## Windows operator acceptance checklist

1. Use a **clean Windows 10 and Windows 11 x64 environment**, not solely the GitHub-hosted build runner. Verify a standard non-admin installation and WebView2 prerequisite setup.
2. Launch and create the owner account; verify no default credentials, no external port binding and a working native WebView window.
3. Use a disposable ledger to exercise the financial acceptance scenarios above and read exported PDF documents.
4. Close/reopen; force-stop and restart; ensure SQLite integrity and data retention, scheduler single-instance behavior and no startup crash loops.
5. Install over an older version with a **copy** of an old test database; verify backup-before-migration and migration compatibility.
6. Uninstall and reinstall; ensure user financial data remains where intended. Verify removal instructions separately if the user chooses to destroy data.
7. Restore an integrity-checked backup into a disposable data folder with the app stopped. Verify record counts, amounts and scores.
8. Confirm expected offline startup with the Windows WebView2 prerequisite already installed. Test CPU/memory and Windows Defender/SmartScreen behavior.
9. Sign release binaries with the appropriate trusted publisher certificate; publish checksums, version, artifact provenance and instructions.

**Release rule:** Do not publish a signed production release until these device and operational checks are recorded as passed. Claims of 100% software correctness cannot be established by source inspection alone.

## Third-party and operations decisions

- Exchange-rate feed: `EXCHANGERATE_HOST_ACCESS_KEY` and provider plan need a real-world test; manual pair entry is supported.
- Backups: configure an off-device/secondary destination, secure access, retention and optional encryption, then demonstrate recovery.
- Distribution: decide versioning, signing identity, private access policy, code-ownership and software-license wording for intended recipients.
- Mobile/PWA: validate viewport, install prompt, keyboard/focus and accessibility in real browsers; financial mutations require a live API.

## CI evidence

[Latest merged-run source and package verification](https://github.com/PerezChris99/kc-ledger/actions/runs/43716306301) (2026-11-15). The current pipeline files are in `.github/workflows/`. After any change, inspect the **new** run results and address regressions.

_Updated 2026-11-15; supersedes the older 2026-11-01 audit and remaining-work list._
