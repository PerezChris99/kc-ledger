# KC Ledger — Vercel-hosted installable PWA + free PostgreSQL (>1 GB)

Last verified: 21 November 2026. The source code and CI prepare the deployment. **A real production domain, provider provisioning, credentials, successful staged deployment, bank/ledger reconciliation and restore drill are separate operations**, not established by a passing build.

## Database recommendation: Prisma Postgres Free

KC Ledger remains 100% Django/psycopg on **ordinary PostgreSQL**. It does **not** need Prisma ORM. The free Prisma Postgres plan (per its November 2026 documentation) offers **2 GB of PostgreSQL storage per workspace, 200,000 operations/month, and up to 50 databases**. It supports pooled application traffic and a separate direct administrative URL. Free tier does **not** provide managed automatic database backups or point-in-time recovery. Choose a region near expected user traffic and verify latency.

Current comparisons:
- **Prisma Postgres:** 2 GB/free workspace (recommended managed PostgreSQL without ORM migration).
- **Neon:** 1 GB/free project in its October 2026 offer; total allowance across projects is not one big database.
- **Aiven:** 1 GB/free service, not above 1 GB.
- **Supabase:** 500 MB/free database quota.
- **Oracle Cloud Always Free VM:** may provide a larger self-managed Postgres install using free block volume allowance, but **the Oracle Autonomous database is Oracle SQL, not drop-in PostgreSQL**. Self-hosting means patching, SSL/firewall, monitoring, offsite backup and restore become your responsibility.

Check official pricing and terms before creating an instance:
- https://www.prisma.io/pricing
- https://www.prisma.io/docs/postgres/database/connecting-to-your-database
- https://neon.com/pricing
- https://supabase.com/pricing
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

### How to provision safely

1. Create a private Prisma Postgres database in your own workspace with a **direct** and **pooled** connection string. Use its native TCP PostgreSQL endpoints; **not** `prisma+postgres://` or a Prisma Accelerate URL.
2. Verify `sslmode=require` or `verify-full` is specified; verify transport, certificate requirements, and the chosen region. Never paste the URL in chat, tickets, GitHub or frontend code.
3. Put the **pooled** string in Vercel Production environment variable `DATABASE_URL`, the **direct** string in `DATABASE_DIRECT_URL`. Pooled host commonly starts with `pooled.db.prisma.io` and direct host with `db.prisma.io`. Both secrets belong only on the backend / protected CI environments.
4. Initialize an **independent** non-production preview database in Vercel Preview. Never expose live clients or monetary records to unreviewed PR previews.
5. Before moving real desktop data to cloud, obtain an independently verified backup and practice restore. Use PostgreSQL direct connection and `pg_dump/pg_restore` with matching client tools; never point this cloud app at an unrelated locally pinned SQLite dataset.
6. Check used space through `SELECT pg_database_size(current_database());` and monitor monthly operations in Prisma's console. Existing dashboard/notification polling is throttled; expensive business intelligence recalculation is still subject to monthly DB operation quotas.
7. Do **not** put Prisma keys, CSRF secrets or Django session secrets into `VITE_*` variables or any compiled JS.

### Vercel setup

Create a **Vite** project `kc-ledger` linked to `PerezChris99/kc-ledger`, root `./`, build command `npm run build`, output directory `dist`. Keep the Python WSGI function `api/index.py` in the same origin. `vercel.json` routes `/api/*` to Django, serves static PWA assets via CDN and an authenticated daily cron route. Existing GitHub Actions deploy automation is intentionally gated and will not automatically publish production without owner configuration.

Set Vercel **Production** private env entries:
- `DATABASE_URL` — pooled TLS PostgreSQL URL
- `DATABASE_DIRECT_URL` — direct TLS URL, consumed **only** by controlled migrations/backup CI (do not include in runtime unless necessary)
- `DJANGO_SECRET_KEY` — independent high-entropy random string, at least 40 chars
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=your-domain.example` (plus current Vercel URL if appropriate)
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.example`
- `LEDGER_USERNAME` and `LEDGER_PASSWORD` — private owner bootstrap credentials
- `CRON_SECRET` — independent high-entropy secret for protected scheduled jobs

Vercel `api/index.py` forces `LEDGER_DEPLOYMENT=vercel`, `LEDGER_DB_ENGINE=postgres` and `RUN_SCHEDULER=0`. It refuses missing/unsafe PostgreSQL configuration. Cookie Secure, HSTS, CSRF and same-origin protections are enabled for HTTPS. The serverless startup path does not attempt to create SQLite directories. PgBouncer pooled connections omit unsupported PostgreSQL startup session options; Django connections have max age zero.

**Important hosting terms:** As of November 2026, Vercel's free **Hobby** plan is restricted to **personal, non-commercial** use. KC Ledger processes business finances; use a Vercel plan whose terms permit commercial use (normally **Pro**) unless Vercel explicitly approves your use case. A free database does not make the hosting free for commercial use.

### Protected deployment

The existing pipeline on a **successful six-job `main` CI run** builds a production deployment with `--skip-domain`, securely backs up the live database using the **direct** endpoint, verifies durable **S3 SSE-KMS** offsite storage with GitHub OIDC, applies Django migrations, tests staged HTTPS API and PWA static assets, then promotes the verified deployment. It fails closed if offsite backup, migration, health/version or PWA assets fail.

This backup pipeline requires an AWS role, private S3 prefix and KMS key; these may incur charges and require your configuration. If you want a wholly free operating footprint, design and test a comparably secure offsite backup destination first; do not bypass backup gates. Prisma Free itself has no automated backups.

Configure GitHub protected `production` environment secrets/variables: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, exact reviewed `VERCEL_CLI_VERSION`, `LEDGER_BACKUP_AWS_ROLE_ARN`, `LEDGER_BACKUP_AWS_REGION`, `LEDGER_BACKUP_S3_URI`, and `LEDGER_BACKUP_KMS_KEY_ID`. Lock deployment to `main` and require owner approval for production. Enable `KC_LEDGER_VERCEL_READY=true` only when the environment and migration/restore checks are ready. In Git integration, prevent early automatic production domain assignment before gated migrations/promotion.

### Test immediately after deployment

```bash
curl -fsSI https://YOUR-DOMAIN/sw.js
curl -fsS https://YOUR-DOMAIN/manifest.webmanifest
curl -fsSI https://YOUR-DOMAIN/pwa/icon-192.png
curl -fsSI https://YOUR-DOMAIN/pwa/icon-512.png
curl -fsSI https://YOUR-DOMAIN/api/health
curl -fsS https://YOUR-DOMAIN/api/version
```

`sw.js` must be JavaScript and noncacheable. The manifest must parse as JSON and expose 192px, 512px and maskable PNGs. The PNG paths must return actual images rather than `index.html`. API responses must not be cached. Then test an authenticated owner session, CSRF-protected writes, page reload, install/uninstall, force offline/reconnect, financial audit events, local AI intelligence, Postgres quotas, and restore on a separate database.

### Installation and local usage

- **Browser-installed cloud PWA:** install from the Vercel HTTPS domain. It launches as a standalone window and exposes all existing features **while connected**. It will not write to the cloud ledger offline.
- **Self-contained local setup:** run `docker compose up --build -d` on your computer, open `http://127.0.0.1:8080` and install that *separate* PWA. With the local Django and Postgres services running, its full backend works without public internet; it does not silently sync to Vercel.
- **Native Windows:** retain the dedicated packaged Windows app when you need a backend that runs without Docker/localhost service management.

**Production acceptance remains conditional.** A browser-installable UI, a checked-in serverless function and a passing CI suite are not substitutes for a real cloud account, backups, credentials, domain/HTTPS, capacity budgeting and clean-device tests.

## Intelligence and offline audit addendum

The additional business-opportunity and frozen-review fields are covered by additive Django migrations 0008 and 0009. They must be applied in the backup-first deployment flow; no history is inferred for older reviewed decisions. The PWA's session isolation, update-reload guard and authenticated cache tests are documented in [audit 32](../history/intelligence-pwa-audit.md). Cloud-installed PWAs continue to need online PostgreSQL for any financial operation. Local Docker/Windows can perform internal analytics offline, **but optional Gemini/Grok advice and third-party FX refresh still require internet**. Never assume these external dependencies function fully without network access.
