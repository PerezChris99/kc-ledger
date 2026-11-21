# KC Ledger — intelligence and PWA deep audit and execution

Audit date: 21 November 2026. Focus: the existing single-owner financial operations product, its Django business/client intelligence, React PWA, local Docker/Windows runtime and Vercel deployment gates. This is not a SaaS or general-purpose social CRM.

## Key architectural corrections implemented

| Concern | Audit finding | Corrective implementation |
| --- | --- | --- |
| Historical strategy outcomes | The engine previously compared reviewed decisions with *today's* live metrics, rewriting the effective verdict with every ledger change | Migration 0008 stores an immutable dated observation, change, direction and evidence-quality at the moment of owner review; later live figures are shown separately |
| False success | An unchanged metric previously satisfied `>= 0` or `<= 0` and was counted as a favorable strategy outcome | A zero delta is now explicitly `unchanged` and has no favorable verdict; never a success |
| Missing baseline | Historical decisions without a real baseline could be evaluated as if a previous number existed | They remain `missing_baseline`, with no fabricated comparison |
| Monetary interpretation | A base currency change can invert an apparent monetary outcome | Goals already store their original currency; new review snapshots also fail closed on missing FX or currency mismatch |
| Future financial records | Future-dated payments/expenses could be included in 'cash collected' and 'recorded cash result' | As-of-date filters exclude future payments, expenses, work hours and future-issued invoices; data quality explicitly counts excluded records |
| Incomplete FX | The engine could still publish historical cash scenarios with source transactions omitted due to absent rates | Forecasts and anomalies are disabled until all relevant conversion rates exist |
| Owner cash planning | Overdue buckets omitted a compact indicator for unpaid invoices coming due shortly | Added `due_next_30_days` and count, explicitly non-guaranteed, and trailing-90-day payer concentration |
| Client confidence | Invoices and their payment rows were previously treated as independent evidence items | Count financial invoice observations once, still use real payment lateness evidence for the risk signals |
| Client intelligence GET load | Opening portfolio/detail re-ran full profile/alert comparison and potential writes on *every* request | Materialized JSON profiles are read for up to 20 minutes, with immediate refresh after recorded signals, on new-client mismatch and periodic job refresh; old stale dates are invalidated |
| Client match cost | The client alert loop compared every previous client to each new client even with no shared adverse signals | Candidate sets are restricted by two intersecting documented signal codes and the 250 most recent references per signal; risk matching is a **bounded review heuristic**, never exhaustive |
| Incident acknowledgements | A dismissed pattern could stay dismissed after additional incidents of the same codes | A change in current/reference incident counts changes the signature, reopens the alert and clears the old review note |
| Sales conversion evidence | Pitch recommendations had no outcome dataset; past wins were unobservable | Migration 0009 adds manually verified opportunity stages, lead source, quoted value, next action and actual won/lost decisions with append-only business-event audit |
| Quote/revenue mixing | Quotes could be mistaken for accounts receivable or a booking | All pipeline values remain separate from the accounting ledger; quote wins do not create invoices, receipts or cash |
| Sparse win rates | A one-off win could be misreported as predictive conversion ability | Observed win share appears only after at least **five closed** cases and is explicitly **not** a client-specific probability |
| Risk of unverified offline writes | Browser caching or background request replay would endanger financial data integrity | Retained network-only API, private-data no-store, offline read-only app shell, and no background mutation queue |
| Session privacy | Old React Query financial data could remain held after explicit server logout or an API 401 | Explicitly clear private query caches and immediately return to login; if remote logout fails, explain that server revocation was not verified |
| PWA update control | Dismissing an update banner could hide a waiting version with no obvious path to apply it | A minimized update reminder remains accessible; every activation asks confirmation before losing unsaved form edits |
| Install discoverability | Desktop users with no `beforeinstallprompt` event had no guidance | Added an explicit installation help entry for Chrome/Edge and Safari rather than a hidden control |

## What the engine actually knows

The deterministic primary engine can explain **recorded cash receipts/expenses and near-term invoice exposure**, past client work behavior, scope and pricing signals, observed trends, owner-defined goals, reviewed experiments and factual sales outcomes. It can challenge a recorded decision based on evidence, cite the rule behind its advice and recommend reversible business practices. Optional Gemini/Grok advice is still a constrained, de-identified, explicitly consented **second opinion**. The AI cannot change financial entries, blacklist a client, guarantee a deal, sign a contract or pay anybody.

### Evidence classification

- **Recorded:** an event, payment, invoice, expense, work hour, goal or documented opportunity stage.
- **Heuristic:** a rule-driven risk index, similarity overlap, historical anomaly or ranked strategy experiment.
- **Scenario:** a mathematical sensitivity to hypothetical cash/cost changes, not a calibrated future probability.
- **Unmeasurable:** missing FX, incomplete cost capture, an absent baseline, fewer than five closed sales outcomes or incomplete settlement records.

No personality, demographic profiling, fabricated market trend or statistically unsupported "AI prediction" is permitted. There is no live competitor-price feed or quantitative demand elasticity.

## Installations and data integrity

| Deployment | Local launch | Data without internet | Separate source of truth |
| --- | --- | --- | --- |
| Browser-installed Vercel PWA | Yes | Only static shell | Managed cloud PostgreSQL |
| Installed localhost Docker PWA | Yes | Yes, if localhost Django + PostgreSQL continue running | Local Docker PostgreSQL volume |
| Existing Windows desktop application | Yes | Yes, if native runtime and configured local DB run | Pinned local PostgreSQL or SQLite |

These databases never silently synchronize. External Gemini/Grok API and live third-party FX refresh still require network access even from the local Docker/Windows app. A browser-installed cloud PWA cannot host Django/Postgres inside browser storage.

The PWA should always be tested against actual authenticated private cache responses and expired sessions, not merely manifest existence. Generated icons, service worker and PWA manifest remain part of CI, and staged Vercel smoke tests block broken rewrites.

## Changes deliberately avoided

- No automatic negative decisions about clients based on risk scores.
- No black-box or pseudo-ML prediction built on five client records.
- No fake P&L, tax liabilities, bank balance, cash runway or business valuation from incomplete accounting.
- No offline financial write queue, silent cross-origin data sync or copying authenticated API responses into Workbox.
- No continuous background model calls that consume paid tokens or the database's free-operation quota.
- No gratuitous Google ADK agents or additional product/scope beyond a single-owner services ledger.

## Evidence still needed for further prediction and commercialization

1. A reconciled chart of accounts and a full expense taxonomy, bank feeds, tax/owner salary and liability records before reporting audited profits or runway.
2. Representative sales opportunities, channel costs, lead dates, actual proposal outcomes and win/loss reasons before serious conversion forecasting; real forecasts need temporal validation and confidence calibration.
3. Written market research with dated sources before claiming external trends or competitor pricing.
4. A reviewable intervention/experiment framework with comparable controls before calling strategy changes causal.
5. A legal and privacy review for customer data retention, consent, automated profiling, data transfer and offline-device protection.
6. Real Vercel/Prisma credentials, private backup location, verified restore drill, preview/production segregation, and staged smoke test before enabling production aliases.
7. Field validation of iOS/Android install/uninstall, background/foreground behavior, home-screen icons, expired-session update, weak Wi-Fi, low storage and standalone UX.
8. Production-scale performance benchmarks using representative (non-customer) data. The financial summary still scans historical rows; the bounded client matching heuristic is **not exhaustive**. New caching and indexes are not substitutes for load testing.

## Verification contract

Run the repository's six existing gates on the final code before merge: Django/SQLite, actual PostgreSQL with backup/restore, frontend lint/Vite PWA verification, Docker Compose, Chromium financial/client/PWA/sales flows, and Windows packaged installer executable smoke. Also verify the dry-run migration check so migrations 0008 and 0009 are complete.

Never call a real production release complete merely because pre-merge CI is green. Deploy only with owner-managed credentials and backups, Vercel project/domain configuration, and the actual environment acceptance checklist.
