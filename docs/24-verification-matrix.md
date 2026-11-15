# Current verification matrix and evidence

KC Ledger is a **single-owner private financial operations console**, not a public bank or multi-tenant SaaS. This document separates *implemented*, *verified by CI*, and *not yet verified on a real device*.

| Layer | Source paths | Automated evidence | Additional acceptance needed |
| --- | --- | --- | --- |
| JSX/frontend | `frontend/`, `vite.config.js`, `package.json` | ESLint, Vite build, npm advisory audit | Real-device UX, complete accessibility |
| Language migration | `frontend/**/*.jsx`, `e2e/*.js` | `npm run verify:source`: no TypeScript source/config | GitHub language statistics may be cached |
| Django/API | `backend/ledger/api*.py` | Django checks, pytest, tests, CSRF and limits | User acceptance on installed product |
| SQLite/models | `backend/ledger/models.py`, migrations | Migration checks, financial tests, packaged SQLite smoke | Upgrades from actual old backups |
| Score and instalments | `backend/ledger/services/` | Determinism, allocation/verdict tests | Trial live data reconciliation |
| Reports | `backend/ledger/services/pdf.py` | PDF tests and Windows bundled PDF smoke | Visual content review and printing |
| FX and targets | `backend/ledger/services/fx.py`, `api_extra.py` | Conversion, missing-rate and query-budget tests | Actual external provider credentials and quota |
| Docker/browser | `docker-compose.yml`, `nginx.conf` | Container build, health and Chromium owner journeys | Deployment-specific networking check |
| Windows desktop | `desktop/` | PyInstaller/Inno Setup build, frozen app self-test | Clean Windows GUI, upgrade, antivirus and code signing |
| Backups | `backend/ledger/management/commands/` | Backup/restore test suite | Operator recovery drill with real copy |

## Mandatory end-to-end workflows

1. Authentication: owner bootstrap, sign-in, throttling, CSRF, unauthorized mutation refusal, logout and expiry.
2. Financial journey: client → invoice → plan → partial payment → full payment; reconcile payment allocation, balance, audit and score at each step.
3. Terminal state: written-off, paid, partial and disputed invoice guard cases, including negative and overpayment requests.
4. Work tracking: engagement/time entry/expense create → edit → archive → restore; confirm API totals and history.
5. Multi-currency: known rate, missing rate, manual override, cashflow and target progress with controlled precision.
6. Recovery: online backup → validate → stop app → restore to disposable database → verify amounts → upgrade and repeat.
7. Native runtime: install → first-run setup → operate → export PDF → restart → upgrade → uninstall without deleting records.
8. Browser/PWA: viewport 375px to desktop, keyboard/focus, reduced motion, install prompt, network-offline behavior that does not create false financial writes.

## Evidence policy

The 2026-11-15 merged base at `df094e3` had a successful five-job GitHub Actions run: [source and package verification](https://github.com/PerezChris99/kc-ledger/actions/runs/43716306301). **Do not label newer code passed until its own commit checks succeed**. Unobserved acceptance is `not verified`, not `passed`.

## Branch and release rules

Develop on `perez`, merge via PR to `main`, sync `perez` to merged `main`, avoid extra permanent branches. Create a signed external distribution release only after the separate physical-device and recovery gates pass.

_Added 2026-11-15._
