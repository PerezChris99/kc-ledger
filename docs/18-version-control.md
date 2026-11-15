# Version control and release governance

The only intended long-lived branches are `perez` (development/integration) and `main` (merged release candidate). Develop and commit on `perez`, run relevant checks, review the diff, open a PR, merge into `main`, and fast-forward `perez` to the merge commit. No orphaned implementation branches or unmerged work.

GitHub Actions **are currently configured and active**. The old October note saying that no CI exists is superseded.

## Required checks

- Backend: Django configuration/migrations; Django test runner; pytest; Ruff check/format; locked Python dependency security review.
- Frontend: locked `npm ci`, lint, Vite production bundle, high-severity npm audit, and JSX-only source check.
- Docker: build and loopback health check.
- Browser: Chromium Playwright workflows.
- Windows: PyInstaller/Inno Setup builder and bundled desktop financial/PDF/SQLite smoke tests.
- Before external distribution: clean OS installation, first-run owner onboarding, upgrade, restart, backup restore, uninstall/retention, actual WebView UI interaction and signing.

Do not equate a green CI suite with a signed production release. Do not change application financial histories to pass a test. Keep commits descriptive and preserve authorship. Avoid force-pushing `main`.

## Language migration

PR #8, merged 2026-11-15, removed TypeScript source, TypeScript configuration and direct TypeScript tooling dependencies. GitHub language percentages can lag behind the live Git tree; the default branch contents are authoritative. `npm run verify:source` checks for accidental reintroduction of TypeScript sources and `tsconfig` files.

_Updated 2026-11-15._
