# KC Ledger — Master Specification

Version 1.0. Canonical product and engineering contract. Owner: KC. Codename: Sentinel.

## Product
KC Ledger is a private financial operations console for one freelance software developer. It is not an invoicing-only tool, spreadsheet, team product or multi-tenant SaaS. It answers: what cash arrived and remains owed; which clients create value; which clients cause financial or operational harm; and what must be done today to collect payment and reduce risk.

Core modules: dashboard; clients and engagements; invoices and payments; instalment plans; insights; Avoid dossiers; immutable event history; targets; calendar; clock; FX converter; settings; PWA shell; PDF exports; reminders and notifications.

## Locked architecture
Backend: Django 5.2, Django Ninja, ORM and migrations. Database: SQLite in WAL mode. Jobs: APScheduler for reminders, ghosting detection, recurring invoice drafts and FX refresh. Frontend: React 18, TypeScript, Vite SPA. Server state: TanStack Query v5. Forms: React Hook Form and Zod. UI primitives: accessible Radix/shadcn-style components. Charts: Chart.js 4. Animation: Framer Motion. PWA: vite-plugin-pwa/Workbox. Deployment: Docker Compose, Gunicorn and nginx/Caddy. PDFs: WeasyPrint. Sounds: Web Audio API synthesis. Explicitly reject Next.js, Redux, GraphQL, Zustand, generic AI starter kits and CI workflows.

## Architectural rules
1. Server/database is the sole source of truth. Service worker caches application assets only; no offline data sync.
2. Each screen uses a view-shaped API request. Client detail aggregates score, factors, invoices, payments, plans, timeline and red flags.
3. Meaningful actions create append-only audit events. Normal deletion is soft deletion.
4. Scoring is deterministic and pure, with no ORM writes inside scoring functions.
5. UI tokens live in frontend/src/styles/globals.css. No ad-hoc component colours or spacing.
6. No fake production numbers; empty data gets proper empty states.
7. A payment consistently updates allocations, invoice balance/status, instalment verdicts, scores, dashboard data and event history.
8. Completion claims require actual checks or explicit disclosure of blocked checks.

## Domain model
Client: name/company/contact/country/currency/status/source/referral/rate/tenure/notes/cached score/timestamps/soft delete. Status: active, paused, archived, blacklisted.
Engagement: client, name, kind (fixed/hourly/retainer/milestone), agreed amount/rate/currency/dates/status/scope/deliverables/revision limit and usage.
Invoice: client, engagement, number/title/issue/due dates/amount/currency/status/paid timestamp/notes. Status: draft, sent, partial, paid, written off, disputed.
Instalment: invoice/client/sequence/label/amount/due date/grace days/status/paid date. Status: pending, paid, late, overdue, waived, missed. PlanMeta tracks deadline and last verdict.
Payment and PaymentAllocation: payment records and explicit allocations to instalments. Expense: category, amount/currency/date, billable status and optional client/engagement. Event: immutable history with related IDs, kind/category/polarity/weight/title/detail/amount/occurred timestamp. SignalType catalogue. TimeEntry: engagement/client/hours/category (billable/revision/admin/meeting). Target: revenue/client/hour goal, amount/currency/deadline. FxRate: base/quote/rate/fetch timestamp/source. Meta: key/value.

## Client health score
Integer 0–100 before explicit penalties. Payment speed 16; on-time rate 16; outstanding risk 10; revenue value 12; loyalty/repeat 8; relationship signals 12; rate health 10; instalment discipline 16. Penalties: 6 per disputed invoice; up to 40 for write-off ratio; 14 per chargeback; 12 per abusive event. Blacklisted clients score zero. Verdict weights: Perfect 1.0, Late 0.5, In progress 0.7, At risk 0.2, Broken 0.0. Tiers: 85–100 Champion; 70–84 Reliable; 55–69 Neutral; 40–54 Caution; 0–39 Avoid. Every factor exposes key, label, max, points, detail and verdict.

## Terminal Ledger design
Dark-first, dense, high-contrast, audit-friendly; avoid generic SaaS-template look, purple gradients, emoji-heavy UI, excessive rounding, decorative shadows and bouncing animations. Semantic colours always pair with text/icons. Tokens: background #0B0F14; surface #111820; elevated #161F2A; border #243140; text #E6EDF3; secondary #9AA7B4; muted #6B7A8A; primary #58A6FF; success #3FB950; danger #F85149; warning #D29922. Define colours centrally only. Inter UI and JetBrains Mono for money, dates, IDs and percentages. Base spacing 4px; cards 8px radius; content max 1440px; sidebar 260px; topbar 60px; mobile padding 16px and 44px touch targets. Dense 12-column desktop grid; mobile tables become cards or horizontal scroll. Minimum body text 14px and mobile labels 12px.

## User experience
Landing: self-host five real Unsplash photos, 1200ms crossfade every 8 seconds, pause on hover, reduced-motion static fallback, translucent dark overlay and concrete copy. Dashboard: six KPI cards, revenue/expense chart, invoice-status chart, aging, client leaderboard, revenue concentration, today's attention, needs-attention table and top-client list; target all key charts at 1440x900. Client details: score and factors, invoices, engagements, plans and timeline. Avoid page: red accent border, detailed flag reasons and PDF dossier export. Persistent topbar: clock, calendar with due-date indicators, FX converter, global search and user menu; sidebar target tracker.

Instalment verdicts: Perfect, Late, In progress, At risk, Broken. FIFO allocation supports partial and excess payments. Sounds are synthesized and user-toggleable; never autoplay. Browser notifications require explicit permission and are suppressed when app is focused. PWA caches assets only.

## Phases
0 bootstrap/docs. 1 models/migrations/admin/demo seed. 2 pure scoring and instalment engines. 3 typed API routers. 4 design system and app shell. 5 landing page. 6 session auth, CSRF and onboarding. 7 dashboard. 8 clients. 9 invoices/payments. 10 instalment UI. 11 insights/Avoid/history. 12 persistent widgets. 13 PWA/mobile. 14 sounds/notifications. 15 documentation, performance, accessibility and acceptance. Build in order; each phase must be tested and documented before merge and tag.

## Version control and acceptance
Only main and perez. Main stays deployable; never commit directly to main, force-push, amend pushed commits or create extra long-lived branches. Use scoped imperative Conventional Commits, meaningful bodies and phase footers. End each phase with backend tests, frontend production build, lint, no unexplained TODO/FIXME or console logging, desktop 1440x900 and mobile 375x667 checks, seed/demo verification, and manual login → dashboard → client → payment → score/timeline test. Merge to main with a phase-labelled merge commit, tag v0.N.0, then sync perez. No CI workflows.

## Changelog
- 2026-10-28: Recorded the canonical product, architecture, domain, design and delivery contract.
