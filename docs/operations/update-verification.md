# Release verification matrix

| Gate | CI automation | External acceptance |
| --- | --- | --- |
| Canonical version | Node and Python read VERSION, public /api/version | Verify Vercel SHA matches Windows tagged build |
| Django web API | SQLite, PostgreSQL, Docker + browser jobs | Actual managed DB, owner login over HTTPS |
| Vercel publish | Workflow only after green CI and ready flag | Vercel project, scoped secrets, deployment protection |
| Production database | Back up before migrate, smoke staged build | Expand/contract + real restore drill |
| Cron | Bearer CRON_SECRET and advisory lock | Runtime duration, provider quota and production logs |
| Desktop build | PyInstaller, Inno, packaged smoke | Clean Windows signing trust, complete GUI acceptance |
| Signed release | Tag matches VERSION, Authenticode signer, checksum | Real issuer certificate and secure distribution |
| Updater | Manifest validation, semver, SHA256, publisher | Verify restart flow, forced minimum and staged rollout |
| Migration rollback | Offline backup before copying binaries, check after migration | Test failed restore and interrupted Inno update |
| Secrets | .env files ignored; no credentials in API metadata | Review CI artifacts, deployment variables and certificate access |

The stable release manifest is available at `https://<your-Vercel-domain>/downloads/latest.json` after production is configured and a stable signed GitHub Release exists.
