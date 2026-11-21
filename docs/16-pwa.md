# KC Ledger — installable progressive web app

## What works and what does not

The KC Ledger React frontend is a standards-based, installable Progressive Web App from **HTTPS on Vercel** or from **local loopback** (such as `http://127.0.0.1:8080`). It provides standalone window launch, real 192x192 and 512x512 PNG assets, a separately padded maskable icon, iOS Apple-touch icon, manifest, revisioned static shell and a service worker, installation guidance, and controlled update notification.

**The installed interface and assets can load offline.** Sensitive data **cannot**: clients, invoices, payments, private notes, charts, business prediction, model advisories, settings and all mutations require a reachable Django server and its database. The app explicitly shows an offline screen, refuses API operations, does **not** cache private API JSON/PDFs, and does **not** queue mutations. No browser-based financial data synchronization has been implemented. A PWA is not the same thing as packaging a PostgreSQL server into the browser.

### Two correct ways to install

| Mode | Install origin | What it connects to | Works without public internet? |
| --- | --- | --- | --- |
| Cloud-installed PWA | `https://your-kc-ledger-domain/` on Vercel | Vercel Django API → dedicated managed PostgreSQL | App shell yes; **business data/features no** |
| Local-server PWA | `http://127.0.0.1:8080/` from the KC Ledger Docker stack | Local Django API → local PostgreSQL Docker volume | **Yes**, as long as that local backend/database is running |
| Existing native Windows installer | Signed Windows application, launched independently | Bundled local Django + pinned PostgreSQL or SQLite | Yes, with local DB and app runtime |

**Important:** The Vercel and local-loopback installations are *separate origins* and *separate data stores*. They do not replicate or automatically synchronize. Never assume local/offline edits made to one database will appear in the other. Moving between them requires explicit, backed-up, verified database migration. Running the app on a phone does not allow that phone to reach your computer's `127.0.0.1` PostgreSQL or Docker backend.

## Web installation

1. Deploy to HTTPS (Vercel production/custom domain) and open the application in Chrome/Edge. Use **Install app** when available, or the browser's Install/Open as App menu.
2. On iPhone/iPad, open in Safari, choose **Share → Add to Home Screen** and **Open as Web App** if offered.
3. Log in normally. The browser install does **not** bypass password, session expiry, CSRF or role checks.
4. When an app update is staged, **Save pending work and choose Update now**. This activates the new verified service worker and reloads; updates do not silently refresh during a financial form edit.

Browser installation options vary by device/browser. iOS Safari does not provide `beforeinstallprompt`, hence the manual guidance. Installing is supported through standard browsers; no app store is required.

## Additional lifecycle/security safeguards

- If an API request returns an expired-session 401, the app immediately hides the private dashboard and discards in-memory financial query results; explicit logout clears private query caches, too.
- A same-origin BroadcastChannel immediately notifies other open KC Ledger tabs of sign-out/session revocation and clears their in-memory private queries. No financial data, session cookie or credential is sent through this channel. Visibility return triggers a fresh authenticated session check even though normal dashboard data is not unnecessarily polled in hidden tabs.
- When the server cannot confirm a logout, the application reports that server-side revocation was **not** verified instead of claiming success.
- A new service worker can be snoozed without losing access to a persistent "Update ready" control; applying it requires explicit confirmation because unfinished form edits may be lost.
- Chrome/Edge install instructions remain discoverable even if no `beforeinstallprompt` event was issued.
- Browser E2E now exercises the authenticated dashboard before asserting that no private API/admin/download responses landed in CacheStorage.

## Cache and security policy

- The generated service worker only precaches the public app shell, hashed JavaScript/CSS, SVG/PNG icons, and public build metadata. Its runtime policy for `/api/`, `/admin/`, `/downloads/`, `/static/` is **NetworkOnly** and all API requests explicitly use `cache: no-store`.
- Service worker navigation fallback is limited to the web app shell; it explicitly excludes sensitive API, administration, download and static routes.
- There is **no cache of authenticated HTTP responses, PDF invoices, JSON, payment records or private dashboard results**, no background sync or financial request retry queue.
- React Query data remains in current-tab memory only and is revalidated on reconnection. It is not serialized to IndexedDB/localStorage for offline access. An offline screen obscures the application while disconnected.
- Credentials stay as secure, HttpOnly cookies on HTTPS. PWA install does not copy sessions or passwords to another device.
- `/sw.js`, `/index.html` and `/manifest.webmanifest` have revalidation headers (Nginx and Vercel); hashed `/assets/` can be cached immutable.
- `skipWaiting: false` and controlled activation avoid abruptly reloading active forms. A stale installed version is not entitled to bypass the backend minimum-version policy.
- App icons are reproducibly generated at build time using `node scripts/generate_pwa_icons.mjs`, not fetched from CDN. The generated `public/pwa/` directory is intentionally ignored by Git.
- WebView2 Windows packaging continues to build the same React frontend, while its desktop process remains a separate application from the browser PWA.

## Automated acceptance

`npm run build` fails unless `dist/manifest.webmanifest`, `dist/sw.js`, all PNG icons and linked entry metadata exist and meet basic invariants. The Chromium suite tests manifest/icon dimensions and a genuine offline reload, plus that CacheStorage contains **no** sensitive `/api/`/admin/download requests.

The Vercel deployment smoke test checks Django health/version SHA **and** that the staged domain actually delivers valid HTML, installable manifest, three icon PNGs and a non-stale JavaScript service worker. This detects CDN rewrites that incorrectly return `index.html` for icons or worker.

Additional manual acceptance before calling a device production-certified: install/uninstall on Chrome/Edge desktop and Android; install from iOS Safari; verify stable signed-in session/cookie lifetime and device time zone; network loss during an unsaved form; reconnection, database restart, migration and long-lived SW update; keyboard navigation/contrast/low-power performance; backup/restore of the authoritative database.

## Versioning and updates

App installation is separate from the signed Windows executable update path. The service worker updates its static files when a new Vite build is deployed; the app offers explicit reload when the new version is waiting. The backend's canonical `VERSION` and SHA remain authoritative, and the web footer shows the version. Server schema migration and deployment promotion are still controlled by the gated Vercel CI job.

## Database and offline operation

- **Cloud PWA:** managed Postgres only; no SQLite on Vercel and no local-file persistence in Functions.
- **Local Docker PWA:** local Postgres 15, running through Docker Compose on `127.0.0.1:8080`. Keep Docker + DB running to use all features without internet. Always back up Docker volumes before updating/removing containers.
- **Offline-only browser use:** intentionally limited to static shell. Full offline editing requires a separate encrypted, conflict-resolved local datastore and explicit reconciliation protocol; not safe to pretend it is implemented for a financial ledger.

See [Vercel + Prisma PostgreSQL runbook](31-pwa-vercel-prisma.md) and [deployment gates](26-updates-and-deployment.md).
