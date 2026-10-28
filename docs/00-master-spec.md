# KC LEDGER — MASTER SPECIFICATION, TECHNICAL BREAKDOWN & BUILD PROMPT

**Document version:** 1.0
**Status:** Canonical — supersedes all prior scope.
**Owner:** KC
**Codename:** Sentinel
**Product name:** KC Ledger

> This document is the single source of truth. Everything below — overview, technical breakdown, design system, phased plan, version control rules, commit conventions, documentation standards, README template, and the master build prompt — is one artifact. Copy this whole block into the repo as `docs/00-master-spec.md` on day one.

---

# PART 1 — NON-TECHNICAL OVERVIEW

## What KC Ledger is

KC Ledger is a **private financial operations console** for a solo software developer running a freelance practice. It is not an invoicing app. It is not a spreadsheet. It is a **client intelligence system** that answers four questions at a glance, every time you open it:

1. **How much money has actually come in, and how much is owed to me right now?**
2. **Which clients are genuinely good for my business — and by how much?**
3. **Which clients are actively hurting me — and exactly how?**
4. **What do I need to do today to get paid and stop the bleeding?**

## What problem it solves

Freelancers lose money in three ways that accounting software never catches:

- **Silent losses.** A client who is 40 days late on a $4,000 instalment is a $4,000 hole in your cashflow. A spreadsheet just shows the invoice as "unpaid." KC Ledger shows it as an *overdue instalment in a plan that has flipped from green to red*, and it reduces that client's health score by a number you can see.
- **Repeated mistakes.** Every freelancer has one client they should have fired a year ago. KC Ledger detects that pattern *before* the next project: broken instalment plans, ignored emails, rate haggling, disputed invoices — all become red flags. When you try to create a new invoice for a red client, the system stops you with a modal.
- **Opportunity cost.** A "reliable" client paying $60/h who accepts everything first time may earn you far more per hour worked than a "$95/h" client who burns 40 hours on revisions. KC Ledger computes the real hourly rate per client and ranks accordingly.

## Who it's for

One person: KC. It runs on a laptop (or a small private server), reachable from any device via the same private network. It is a PWA — installable on phone and desktop like a native app. No login sharing. No team features. No SaaS multi-tenancy. This is a **personal cockpit**.

## What "done" looks like

- Landing page loads with a translucent hero and a rotating slideshow of real financial operations imagery.
- Dashboard opens in under 1 second with live KPIs, live charts, and a "today" panel of the 5 things that most need your attention.
- Every client has an explainable 0–100 health score with a full breakdown you can read.
- Instalment plans track the five verdicts — **Perfect, Late, In progress, At risk, Broken** — with the plan flipping colour in real time as instalments are paid or missed.
- A calendar, clock, currency converter, and target tracker live persistently in the app shell.
- Every currency figure, every score, every chart is derived live from the database — never hardcoded.
- Notification and alarm sounds fire on meaningful events (invoice paid, instalment overdue, plan verdict flip).
- Works offline for the app shell. Works on a 375px phone as well as a 4K monitor. Both feel native.
- The whole product looks like a **terminal-inspired financial operations console** — dense, precise, dark, audit-friendly — not like a "modern AI-generated SaaS template."

---

# PART 2 — TECHNICAL ARCHITECTURE

## Stack decision (locked)

| Layer | Choice | Rationale |
|---|---|---|
| Backend framework | **Django 5.x** | ORM, admin, migrations, auth — all first-class for a data-heavy single-user tool |
| API layer | **Django Ninja** | FastAPI-style typed routes inside Django; auto OpenAPI for TypeScript codegen |
| Database | **SQLite (WAL mode)** | Single-user, one file, trivial backups (`cp ledger.db`) |
| Background jobs | **APScheduler** (in-process) | Reminders, ghosting detection, recurring invoices, FX refresh |
| Frontend framework | **React 18 + TypeScript + Vite** | Type-safe, fast dev loop, no SSR needed |
| Server state | **TanStack Query v5** | Handles caching, invalidation, background refetch, polling |
| Forms | **React Hook Form + Zod** | Dynamic rows, complex validation, type-safe schemas |
| UI primitives | **shadcn/ui (Radix)** | Accessible dialogs, dropdowns, selects, popovers, toasts — deeply customizable |
| Charts | **Chart.js v4 via react-chartjs-2** | Full control, no magic, canvas-based (fast) |
| Animations | **Framer Motion** | Precise control over transitions; small, tree-shakeable |
| PWA | **vite-plugin-pwa (Workbox)** | Manifest generation, asset caching, install prompt |
| Icons | **Lucide + 6 custom-drawn glyphs** | Avoid the "AI-default icon set" tell; hand-draw anything critical |
| Deployment | **Docker Compose → gunicorn + nginx (or Caddy)** | One command up, one command backup |
| FX rates | **exchangerate.host** (free tier) via APScheduler job; manual override table | Fully dynamic currency conversion |
| PDF export | **WeasyPrint** (server-side, from same CSS tokens) | Invoice/statement PDFs that look exactly like the app |
| Sounds | **Web Audio API synth tones** (no external files) + optional preloaded samples | Notification blips, alarm for overdue |

**Explicitly rejected:** Next.js (no SSR needed), Redux (TanStack Query covers it), GraphQL (REST is simpler here), Zustand (query cache is the store), Tailwind's prebuilt component kits beyond shadcn (would look generic), any "AI Starter Kit" or "Modern SaaS Template."

## High-level architecture
┌──────────────────────────────────────────────────────────────┐
│ Browser / PWA (installable) │
│ │
│ React SPA (Vite) │
│ ├── Landing page (hero slideshow, glassmorphism) │
│ ├── App shell (sidebar, topbar, calendar, clock, FX, target)│
│ ├── Feature routes (dashboard, clients, invoices, plans, …) │
│ ├── TanStack Query cache │
│ └── Service worker (asset caching only) │
└───────────────────────┬──────────────────────────────────────┘
│ HTTPS / JSON (same-origin via nginx)
┌───────────────────────▼──────────────────────────────────────┐
│ Django 5.x backend │
│ │
│ ├── Django Ninja routers (typed, OpenAPI at /api/openapi) │
│ ├── ORM models + migrations │
│ ├── Django Admin (data browser, filters, inlines) │
│ ├── Services layer (pure Python, fully unit-tested) │
│ │ ├── scoring.py — health score │
│ │ ├── instalments.py — allocation + verdicts │
│ │ ├── cashflow.py — 90-day forecast, tax reserve │
│ │ ├── reconciliation.py — bank CSV matching │
│ │ ├── fx.py — currency conversion │
│ │ └── targets.py — goal progress + projections │
│ ├── Jobs (APScheduler) │
│ │ ├── reminders.py — daily nudges │
│ │ ├── ghosting.py — auto-signal silence │
│ │ ├── recurring.py — retainer drafts │
│ │ └── fx_refresh.py — daily rate pull │
│ └── Event log (append-only audit trail) │
└───────────────────────┬──────────────────────────────────────┘
│
┌─────────▼─────────┐
│ SQLite (WAL) │
│ data/ledger.db │
└───────────────────┘

text

## Guiding architectural principles

1. **The server is the only source of truth.** No offline-first sync. No IndexedDB mirror. The PWA caches the app shell; data always comes from Django. This eliminates an entire class of sync bugs.
2. **One endpoint per screen.** `GET /api/clients/{id}` returns the *entire* client detail — score, breakdown, invoices, payments, plans, timeline, red flags. Never more than one request per route transition.
3. **The event log is append-only.** Every meaningful action writes an immutable row. Nothing is deleted — soft-delete only. History is forever.
4. **The scoring engine is pure and testable.** No ORM writes inside scoring. No side effects. Given a snapshot of data, it returns a deterministic result. This is what makes it trustworthy.
5. **The design system is enforced by tokens.** Every colour, spacing, radius, and font size is a CSS custom property. No hardcoded `#hex` anywhere in components. No "close enough" magic numbers.
6. **Every number on screen comes from the API.** No hardcoded demo data baked into React. If the DB is empty, the UI shows a proper empty state, not sample numbers.
7. **Every commit is a working commit.** The `main` branch is always deployable. If a feature isn't finished, it lives on `perez` until it is.

## Data model (final)

```python
# Django ORM models — conceptual representation

Client
  id, name, company, email, phone, country, currency,
  status (active|paused|archived|blacklisted), source, referred_by,
  rate, rate_unit, started_at, notes,
  score (cached), score_updated_at,
  created_at, updated_at, deleted_at

Engagement
  id, client_id, name, kind (fixed|hourly|retainer|milestone),
  agreed_amount, rate, currency, start_date, end_date,
  status (active|done|cancelled|paused), scope_notes,
  sow_deliverables (JSON), revision_limit, revisions_used,
  created_at, updated_at, deleted_at

Invoice
  id, client_id, engagement_id, number, title,
  issue_date, due_date, amount, currency,
  status (draft|sent|partial|paid|written_off|disputed),
  paid_at, notes, created_at, updated_at, deleted_at

Instalment
  id, invoice_id, client_id, seq, label, amount,
  due_date, grace_days, status (pending|paid|late|overdue|waived|missed),
  paid_on, created_at, updated_at, deleted_at

PlanMeta
  invoice_id (PK), plan_deadline, last_verdict, notes,
  created_at, updated_at

Payment
  id, invoice_id, client_id, amount, paid_on,
  method, reference, note, created_at, deleted_at

PaymentAllocation
  id, payment_id, instalment_id, amount, created_at

Expense
  id, client_id, engagement_id, category, amount, currency,
  spent_on, billable, note, created_at, deleted_at

Event                      # append-only audit log
  id, client_id, engagement_id, invoice_id, payment_id,
  kind, category (money|behaviour|comms|delivery|relationship),
  polarity (-1|0|+1), weight, title, detail, amount,
  occurred_at, created_at, deleted_at  # deleted_at never set in normal use

SignalType                 # signal catalogue
  kind (PK), label, category, polarity, weight, icon

TimeEntry                  # enables effective hourly rate
  id, engagement_id, client_id, hours, category (billable|revision|admin|meeting),
  started_at, note, created_at, deleted_at

Target                     # goal visualization
  id, name, type (revenue|clients|hours),
  amount, currency, deadline, created_at, deleted_at

FxRate
  id, base, quote, rate, fetched_at, source

Meta
  key (PK), value
Scoring engine (final specification)
Score is a 0–100 integer computed from 8 weighted factors minus explicit penalties.

Factor	Max pts	What it measures
Payment speed	16	Amount-weighted average days past due
On-time rate	16	% of settled invoices paid within terms
Outstanding risk	10	% of billed currently overdue
Revenue value	12	Log-scaled lifetime collected, relative to best client
Loyalty & repeat	8	Tenure × engagement count
Relationship signals	12	Weighted sum of positive vs negative events
Rate health	10	Accepted increases vs haggling events
Instalment discipline	16	Plan verdict ratio
Penalties (subtracted after factors):

6 pts per disputed invoice

Up to 40 pts for write-off ratio

14 pts per chargeback

12 pts per abusive event

Full zero if client.status == 'blacklisted'

Plan verdicts contribute to Instalment Discipline as:
Perfect = 1.0 · Late = 0.5 · In progress = 0.7 · At risk = 0.2 · Broken = 0.0

Tier thresholds:

85–100 → Champion (gold)

70–84 → Reliable (green)

55–69 → Neutral (blue)

40–54 → Caution (amber)

0–39 → Avoid (red)

Every factor emits {key, label, max, pts, detail, verdict} — the client detail page renders this verbatim. No black box.

PART 3 — DESIGN SYSTEM: "TERMINAL LEDGER"
This is the canonical design language. It supersedes all previous colour schemes. Every component, every screen, every chart obeys these tokens.

Design philosophy
KC Ledger should feel like a calm financial operations console: a precise ledger, a monitoring dashboard, and an audit trail in one. Dark-first, high-contrast, dense but readable. Green means profit/pass. Red means loss/fail. Amber means pending/warning. Blue means primary action/info. Nothing else is coloured. Colour is information, not decoration.

This is explicitly NOT the "AI-generated SaaS template" look. No purple gradients, no soft bouncing springs, no emoji everywhere, no drop shadows, no 20px border radius, no centred hero with floating cards, no default Lucide icons scattered around, no generic 3-column feature grid. Read the DO/DON'T list at the end of this section before writing any CSS.

Colour tokens
css
/* Dark theme (default) */
:root {
  /* Surfaces */
  --bg:              #0B0F14;   /* app background */
  --surface:         #111820;   /* card */
  --elevated:        #161F2A;   /* modal, dropdown */
  --input:           #0D141C;
  --hover-row:       #1B2530;

  /* Borders */
  --border:          #243140;
  --border-strong:   #2F3F52;

  /* Text */
  --text:            #E6EDF3;
  --text-secondary:  #9AA7B4;
  --text-muted:      #6B7A8A;

  /* Semantic */
  --primary:         #58A6FF;
  --primary-hover:   #79B8FF;
  --primary-surface: rgba(88,166,255,0.12);

  --success:         #3FB950;
  --success-surface: rgba(63,185,80,0.12);

  --danger:          #F85149;
  --danger-surface:  rgba(248,81,73,0.12);

  --warning:         #D29922;
  --warning-surface: rgba(210,153,34,0.12);

  --neutral-badge:   #8B949E;

  /* Charts */
  --chart-grid:      #263241;
  --chart-revenue:   #58A6FF;
  --chart-profit:    #3FB950;
  --chart-loss:      #F85149;
  --chart-forecast:  #D29922;

  /* Effects */
  --focus-ring:      #58A6FF;
  --backdrop:        rgba(0,0,0,0.65);
}
Optional light theme (via [data-theme="light"] on <html>):

text
--bg: #F6F8FA; --surface: #FFFFFF; --elevated: #FFFFFF;
--border: #D0D7DE; --text: #1F2328; --text-secondary: #59636E;
--input: #F6F8FA;
Semantic colours (green, red, amber, blue) stay identical.

Colour usage rules (non-negotiable)
Green is NEVER the primary button colour. Green is only for: profit amounts (+$4,200), paid status, healthy scores, positive deltas.

Red is only for: losses (−$1,300), overdue status, destructive actions, broken plans, negative deltas. Red fill only in destructive confirmation modals.

Amber is only for: pending, due-soon, forecast lines, "at risk" plan verdict, unmapped imports.

Blue is the primary action colour. Buttons, links, focus rings, active nav, info badges.

Never rely on colour alone. Every status is colour + icon + text label. "Paid ✓" not just green. "Overdue ⚠" not just red.

Surfaces stay neutral. If a card is not a status, it does not have a coloured background.

Typography
css
--font-ui:    Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
--font-mono:  "JetBrains Mono", "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;

/* Scale — deliberately large for readability */
--text-xs:   11px;   /* labels, badges */
--text-sm:   12.5px; /* meta, timestamps */
--text-base: 14px;   /* body, table text */
--text-md:   15px;   /* form inputs */
--text-lg:   17px;   /* section titles */
--text-xl:   22px;   /* page subheadings */
--text-2xl:  28px;   /* page titles */
--text-3xl:  34px;   /* KPI values */
--text-4xl:  44px;   /* hero numeric values */
Rules:

All money, percentages, dates, IDs, table figures: --font-mono with font-variant-numeric: tabular-nums. No exceptions.

Headings: Inter, 600–700, tight tracking (letter-spacing: -0.02em).

Labels above inputs: --text-xs, uppercase, letter-spacing: 0.06em, --text-muted.

KPI values: mono, --text-3xl, weight 600.

Timestamps and IDs: mono, --text-sm, --text-muted.

Never use font-size below 11px anywhere. Mobile minimum body: 14px. Mobile minimum label: 12px.

Spacing & layout
Base unit: 4px. Everything is a multiple of 4.

Common values: 4, 8, 12, 16, 24, 32, 48, 64.

App shell: sidebar 260px (collapses to 76px on icon-only mode), topbar 60px, content max-width 1440px, content padding 32px desktop / 16px mobile.

Grid: CSS Grid 12-column responsive with gap: 16px (24px on wide).

Card: border: 1px solid var(--border), border-radius: 8px, no box-shadow (except modals/dropdowns which use 0 8px 24px rgba(0,0,0,0.5)).

Table rows: 48px height desktop, 56px mobile (for touch). Sticky header. Right-aligned amounts. No zebra stripes. Hover row: var(--hover-row).

Layout philosophy — side-by-side, no excessive scroll
The user has one core complaint about dashboards: wasted vertical space. Fix it structurally:

Dashboard uses a 12-column grid with asymmetric cells — never a single stacked column on wide screens. Example: [KPI strip: 12 cols] → [Revenue chart: 8 cols | Status doughnut: 4 cols] → [Aging: 4 | Leaderboard: 4 | Concentration: 4].

All charts fill their card. The <canvas> element receives width: 100%; height: 100% and the card gives it a fixed aspect ratio or a min-height. No letterboxed charts with 40% empty padding.

Client detail: [main content: 8 cols | sidebar cards: 4 cols].

Insights: 2×2 grid on desktop, single column on mobile.

Zero decorative vertical whitespace between sections — use the grid gap.

On mobile everything collapses gracefully but never looks like a stretched desktop page. Cards go full-width, tables become horizontal-scroll or card-list views.

Component specifications
KPI card
text
┌─────────────────────────────────┐
│ COLLECTED            [muted xs] │
│ $124,300.00          [mono 3xl] │
│ ▲ +$8,200 vs last  [pill green] │
│ ▁▂▃▅▆▇█              [sparkline]│
└─────────────────────────────────┘
Label: uppercase, muted, xs

Value: mono, 3xl, weight 600, tabular-nums

Delta pill: +$X with arrow icon + text label; green/red/amber by direction and meaning

Sparkline: 40px tall, single-colour, no axes

Never colour the whole card. Colour lives only in the delta pill and sparkline.

Status badge
text
PASS ✓     PASS (green, check icon)
OVERDUE ⚠  OVERDUE (red, warning icon)
PENDING ◷  PENDING (amber, clock icon)
DRAFT ◻    DRAFT (blue/grey, square icon)
border-radius: 4px (not pill-shaped — that's an AI-template tell)

Padding: 4px 8px

Font: mono 11px, uppercase, letter-spacing: 0.05em

Buttons
Primary: background: var(--primary); color: #0B0F14; — blue filled, dark text.

Secondary: transparent, border: 1px solid var(--border-strong), color: var(--text).

Destructive: border: 1px solid var(--danger); color: var(--danger). Fill only in the confirmation modal.

Success action (rare — e.g. "Mark reconciled"): border: 1px solid var(--success); color: var(--success).

Border radius: 6px — not 20px, not pill.

Padding: 10px 16px desktop, 12px 18px mobile (larger touch target).

Hover: 150ms background shift only, no scale, no bounce.

Focus: 2px blue ring, 2px offset, always visible.

Inputs
Background: var(--input), border: 1px solid var(--border), radius: 6px.

Label above (11px uppercase muted). Helper text below (12.5px muted). Error text red with ⚠ icon.

Focus: border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-surface).

Font: 15px in the field itself (larger for readability).

Amount fields: mono font, right-aligned, tabular-nums.

Navigation
Sidebar item: 44px tall, 12px horizontal padding, radius 6px.

Active state: 3px blue left border + background: #151F2B.

Icons: 18px, stroke 1.5, from Lucide but custom-tinted (never default Lucide blue).

Hover: background: #151F2B at 60% opacity.

Labels: 14px, weight 500.

Toasts
Surface: var(--elevated).

3px left border in semantic colour.

Icon + short message + optional action link.

Fade in from bottom-right, 200ms.

Auto-dismiss in 4 seconds unless the message requires action.

Modals
Surface: var(--elevated), radius: 8px, shadow: 0 8px 24px rgba(0,0,0,0.5).

Backdrop: rgba(0,0,0,0.65).

Enter animation: 200ms ease-out, scale 0.98 → 1, opacity 0 → 1. No spring.

Focus trap. Escape closes. Backdrop click closes (except destructive modals — require explicit action).

Tables
Sticky header (position: sticky; top: 0).

Row height 48px desktop / 56px mobile.

Border-bottom 1px solid #1a2438 (dimmer than card border).

Amounts right-aligned, mono, tabular-nums, colour by sign (+ green, − red, neutral muted).

Hover: background: var(--hover-row).

No zebra striping — that's an Excel/AI-template artifact.

Sort indicators: subtle chevron next to column name, 12px.

Charts
Fill the card completely. <canvas> gets width: 100%; height: 100%. Card has fixed height (250px standard, 320px tall).

Grid lines: #263241, 1px.

Axis labels: #6B7A8A, 11px.

Revenue line: --chart-revenue.

Profit line: --chart-profit.

Expenses/loss: --chart-loss.

Forecast: --chart-forecast, dashed.

Area fills: only as low-opacity wash (rgba(63,185,80,0.10)).

Tooltips: --elevated surface, 1px border, mono values.

Every chart has a direct label or legend — never rely on colour alone for meaning.

No 3D, no gradients in chart lines, no animation beyond 400–600ms draw-in.

Motion & interaction
All transitions 150–200ms ease-out. Nothing bounces. Nothing springs.

Page transitions: fade + 8px upward drift, 200ms.

Number counters: tick smoothly from 0 to value over 600ms when a KPI card first mounts (only once — never re-tick on every poll).

Chart reveal: 400ms draw-in on first load only.

Hover: 150ms background and border-color shift.

Focus: 0ms (instant).

Modal: 200ms scale + fade.

Toast: 200ms slide-in from right.

Respect prefers-reduced-motion: all transitions become instant.

No autoplay animations longer than 800ms.

Glassmorphism (landing page only — subtle)
The user asked for glassmorphism. Apply it precisely and sparingly:

Only on the landing page hero overlay and the sticky top bar.

Backdrop filter: blur(20px) saturate(140%).

Background: rgba(11,15,20,0.55).

Border: 1px solid rgba(255,255,255,0.08).

Nowhere else. Dashboard cards, modals, forms, tables — all use solid surfaces. Slathering glass everywhere is the #1 "AI vibe coded" tell.

DO / DON'T (read before every screen)
DO:

Dark neutral surfaces with 1px borders

Semantic status colours only

Mono numbers, tabular-nums everywhere money appears

Dense tables with sticky headers

Clear focus states

Explicit +/− signs on amounts

Real data from the DB, always

Icons that match the meaning (✓ paid, ⚠ overdue, ◷ pending)

Original custom glyphs where they carry meaning

DON'T:

Use green as the main brand/button colour

Use red for non-destructive primary actions

Use gradients as decoration (only on chart area fills at ≤10% opacity)

Use colour alone to convey meaning

Use playful rounded "fintech" visuals (radius 20px+)

Use low-contrast grey text for critical values

Use purple/pink as an accent

Use emoji as UI icons in data tables (use real glyphs or Lucide)

Use "hero with floating cards over abstract blob background"

Use default shadcn/Lucide styling without custom tokens

Use box-shadow on cards

Use zebra striping on tables

Use animated counters on every render

Use transform: scale() on hover for buttons

Use the phrase "elevate your" / "seamless" / "empower" in any copy

Use a font smaller than 11px

PART 4 — UI/UX SPECIFICATION
Landing page (public, pre-auth)
Purpose: Show KC — and only KC — what this tool is. Not a marketing site. Not a sales page. A tool's front door.

Layout:

text
┌──────────────────────────────────────────────────────────────┐
│  KC LEDGER          [logo]     [Sign in]                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│      ┌──────────────────────────────────────┐                │
│      │                                       │                │
│      │   Translucent hero with rotating      │               │
│      │   full-bleed financial operations     │               │
│      │   imagery behind (backdrop-filter     │               │
│      │   blur + rgba overlay 0.55)           │               │
│      │                                       │               │
│      │   "YOUR BUSINESS,                     │               │
│      │    GUARDED."                          │               │
│      │                                       │               │
│      │   A private operations console for    │               │
│      │   freelance developers. Knows who     │               │
│      │   owes you, who's wasting your time,  │               │
│      │   and what to do next.                │               │
│      │                                       │               │
│      │   [Open Console →]   [See features]   │               │
│      │                                       │               │
│      └──────────────────────────────────────┘                │
│                                                              │
│   ↓ (smooth scroll)                                          │
│                                                              │
│   ─── WHAT IT DOES ───                                       │
│   [Side-by-side 2-col grid, minimal copy, real feature cards]│
│                                                              │
│   ─── WHO IT'S FOR ───                                       │
│   [Side-by-side 2-col: image | copy]                         │
│                                                              │
│   ─── THE SYSTEM ───                                         │
│   [3-col grid of technical capabilities]                     │
│                                                              │
│   ─── [Open Console →] ───                                   │
│                                                              │
│   footer                                                     │
└──────────────────────────────────────────────────────────────┘
Hero slideshow:

Real stock photography — financial operations, developer at work, ledgers, trading screens, spreadsheets, code on screen, a person at a desk with an organized wallet/invoice stack. NOT abstract blobs, NOT 3D renders, NOT AI-generated faces.

Source: Unsplash (unsplash.com) — free license, high-quality real photography. Download 5 images locally into frontend/src/assets/hero/. Do not hotlink.

Suggested searches: "financial dashboard", "developer working laptop", "invoices on desk", "accountant spreadsheet", "analytics screen".

Rotate every 8 seconds. Crossfade transition 1200ms. Pause on hover. Respect prefers-reduced-motion — if set, show first image only, no rotation.

Translucency stack:

text
<img> (full-bleed, object-fit: cover, opacity 1)
<div backdrop overlay> background: rgba(11,15,20,0.62)
<div hero-content> with backdrop-filter: blur(20px) saturate(140%)
                   background: rgba(11,15,20,0.35)
                   border: 1px solid rgba(255,255,255,0.08)
Hero headline: mono, --text-4xl (44px), tracking tight, uppercase-lite ("Your business, guarded.")

Subhead: --text-lg, --text-secondary

CTAs: primary blue filled + secondary outlined.

No floating cards, no 3D mockup, no scroll indicator arrow with bounce.

Smooth scroll: html { scroll-behavior: smooth; } plus @media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }. Framer Motion whileInView for section reveals, 200ms, no bounce.

Landing page restrictions:

No emoji. Not in headings, not in bullets, not in buttons.

No "supercharge", "unleash", "elevate", "seamless", "empower", "revolutionary".

Copy is concrete: "Tracks instalment plans and flags clients who break them." Not: "Effortlessly manage your client relationships."

Every section header is a real label: WHAT IT DOES, WHO IT'S FOR, THE SYSTEM, AUDIT TRAIL. Uppercase, muted, mono, 11px, letter-spacing: 0.1em.

App shell (post-auth)
text
┌───────────────────────────────────────────────────────────────────┐
│ ┌────────────┐ ┌──────────────────────────────────────────────┐  │
│ │            │ │ [search]       [clock] [calendar] [FX] [user]│  │
│ │  KC        │ ├──────────────────────────────────────────────┤  │
│ │  LEDGER    │ │                                              │  │
│ │            │ │  Main content (12-col grid)                  │  │
│ │ ────────   │ │                                              │  │
│ │ ▸ Dashboard│ │                                              │  │
│ │   Clients  │ │                                              │  │
│ │   Invoices │ │                                              │  │
│ │   Plans    │ │                                              │  │
│ │   Insights │ │                                              │  │
│ │   Avoid    │ │                                              │  │
│ │   History  │ │                                              │  │
│ │   Settings │ │                                              │  │
│ │            │ │                                              │  │
│ │ ────────   │ │                                              │  │
│ │  Target    │ │                                              │  │
│ │  [progress]│ │                                              │  │
│ └────────────┘ └──────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
Topbar widgets (always visible, live):

Clock: HH:MM:SS mono, updates every second, timezone from settings.

Calendar button: opens a popover calendar. Days with instalment due dates show a small blue dot. Overdue days show a red dot. Clicking a day shows a list of invoices/instalments tied to that date.

FX button: opens a currency converter popover. Two inputs (from / to), live rates from FxRate table (refreshed daily), one-line result. Converter is also auto-applied to any multi-currency figure in the app (client detail header shows both native and base currency).

Search: global search across clients, invoices, payments, events (via SQLite FTS5 index).

User: settings dropdown.

Sidebar bottom — Target widget:

Persistent progress ring or bar showing current target: e.g. $42,300 / $80,000 by Jun 30 → 53%.

Click to open target detail modal. Multiple targets supported. Show pace: "on track / 12 days behind / projected to hit 8 days late."

Dashboard
12-column grid, no vertical scrolling beyond one viewport at 1440×900:

text
Row 1: [KPI strip — 6 cards, each 2 cols]
       Collected | Outstanding | Overdue | Expenses | Net profit | Avg. payment

Row 2: [Revenue vs expenses chart — 8 cols] [Invoice status doughnut — 4 cols]

Row 3: [Aging — 4 cols] [Client score leaderboard — 4 cols] [Revenue concentration — 4 cols]

Row 4: [Today panel — 6 cols: instalments due, invoices crossed due, ghosted clients]
       [Needs attention table — 6 cols]

Row 5: [Client health list — 12 cols, dense table, top 8 clients]
Every chart fills its card completely (canvas width:100%; height:100%).

Client detail page
text
Row 1: [Header full-width — name, score chip, badges, red flags, actions]

Row 2: [KPI strip — 6 cards full-width]

Row 3: [Score breakdown — 8 cols, 8 factors with bars + details]
       [Score radar chart — 4 cols]

Row 4: [Invoices table — 8 cols]
       [Engagements + signals mix — 4 cols]

Row 5: [Instalment plans — 12 cols, one block per plan]

Row 6: [Full timeline — 12 cols, grouped by month]
Instalment plan block
text
┌───────────────────────────────────────────────────────────────────┐
│  INV-1003 · Phase 2 — billing              [Edit plan] [Record]   │
│                                                                    │
│  ✓ Perfect    Every instalment paid by its due date               │
│  $8,000 / $8,000 · deadline 30 Apr 2026                           │
│  ─────────────────────────────────────────────────────────────    │
│  ● Deposit        $2,000    15 Jan    paid on time     $2,000     │
│  ● Sprint 1       $2,000    15 Feb    paid on time     $2,000     │
│  ● Sprint 2       $2,000    15 Mar    paid on time     $2,000     │
│  ● Final          $2,000    15 Apr    paid on time     $2,000     │
└───────────────────────────────────────────────────────────────────┘
Verdict pill colours per rules: perfect green, late amber, at risk orange (--warning), broken red, in progress blue.

Avoid page
text
┌───────────────────────────────────────────────────────────────────┐
│  DO NOT WORK WITH                                                 │
│  These clients have cost you money, time, or both.                │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  AMANDA COLE                              [AVOID · Score 12] │  │
│  │  Cole & Partners · acole@colepartners.com                    │  │
│  │                                                              │  │
│  │  ⛔ Disputed invoice — $9,000                                │  │
│  │  ⛔ Chargeback initiated                                     │  │
│  │  ⛔ Wrote off $9,000                                         │  │
│  │  ⚠ Ghosted mid-project for 6 weeks                           │  │
│  │  ⚠ Continuous scope creep, no change orders                 │  │
│  │  ⚠ Abusive emails to me and my partner                       │  │
│  │                                                              │  │
│  │  Lifetime collected: $9,000 · Written off: $9,000            │  │
│  │  Effective cost: −$0 net (you broke even before your time)   │  │
│  │                                                              │  │
│  │  [View full history →]  [Export dossier PDF]                 │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
Red left border, red ACCENT (not the whole card). Every flag shows an icon + label + detail.

Mobile (375px)
Sidebar collapses to bottom tab bar: Dashboard · Clients · Invoices · Plans · More.

Topbar compresses: clock shrinks to HH:MM, calendar + FX + user collapse into ⋯ menu.

All grids become single-column.

Tables switch to card list view (one card per row).

Minimum touch target 44×44px.

Minimum body font 14px. Minimum label 12px.

Instalment dots become full-width rows.

Plan editor modal becomes a full-screen sheet.

Charts: aspect ratio forced to 1.6:1 minimum, fill screen width minus padding.

Landing page hero on mobile: slideshow still runs, hero content becomes full-width card, text sizes scale down but never below 20px for the main headline.

Sounds & notifications
Sound design: use the Web Audio API for synthesized tones — no external audio files. One module lib/sounds.ts with named presets:

notifySuccess() — two short sine tones (C5, E5), 120ms, 25% gain. Fires on: payment recorded, invoice paid, plan flipped to perfect.

notifyInfo() — single A4 sine, 100ms. Fires on: soft reminder, target reached 50%.

notifyWarning() — two D4 tones, 180ms apart, 30% gain. Fires on: instalment due in 3 days, invoice crossed due date.

alarmOverdue() — 3-tone descending alarm (G4, E4, C4), 400ms total, 40% gain. Fires on: plan flipped to broken, invoice 30+ days overdue.

All sounds respect a user toggle in Settings (per-category).

All sounds respect prefers-reduced-motion → play at 50% gain.

Never autoplay on page load. Only fire on genuine state changes triggered by an API response or WebSocket-style poll.

Implemented as AudioContext oscillators, disposed after use. Zero network requests.

Browser notifications (via Notification API, gated behind explicit permission request in Settings):

"Instalment due in 3 days — Priya Raman, $2,000"

"Invoice crossed due date — INV-4002, Dmitri Volkov"

"Plan flipped to broken — INV-4001"

Suppressed when the tab is focused (in-app toast is enough).

PART 5 — PHASED DEVELOPMENT PLAN
Each phase is self-contained, ends with a merge to main, and leaves the app in a deployable state. No CI workflows are configured — human discipline enforces the green-before-merge rule.

Phase 0 — Bootstrap (1 weekend)
Branch: perez
Goal: Empty repo → running skeleton → merged to main.

Repo created with .gitignore, LICENSE, README.md (using the template below), docs/00-master-spec.md (this file).

docker-compose.yml with Django + nginx (or Caddy) + SQLite volume.

pyproject.toml (Django, Django Ninja, APScheduler, pandas, WeasyPrint, psycopg for later, ruff, pytest).

package.json (Vite, React, TS, TanStack Query, RHF, Zod, Tailwind, shadcn, Framer Motion, Chart.js, react-chartjs-2, vite-plugin-pwa, Lucide).

frontend/vite.config.ts with /api proxy.

config/settings.py, config/urls.py, manage.py.

Base docs/01-setup.md, docs/02-architecture.md.

Empty App.tsx that renders "KC Ledger".

Merge to main with message: chore(bootstrap): scaffold Django + React monorepo with Docker Compose and design tokens.

Phase 1 — Data layer (1 weekend)
All Django models (from Part 2).

Migrations created and applied.

Admin registered for every model with filters, search, inlines where useful.

SignalType catalogue seeded via data migration.

management/commands/seed_demo.py — port the demo clients (Nadia, Marcus, Priya, Dmitri, Amanda, Tobias), their invoices, payments, expenses, plans, events.

Tests: model constraints, soft-delete behaviour, admin loads.

Docs: docs/03-data-model.md, docs/04-seeding.md.

Merge: feat(models): add full data layer with clients, invoices, instalments, events, and demo seed

Phase 2 — Scoring engine (1 weekend)
services/scoring.py — pure functions. No ORM writes.

services/instalments.py — allocation, recalc, verdict.

services/verdicts.py — the 5-state machine.

Tests: 30+ cases covering edge cases (partial payments, over-payment, early payers, chargebacks, blacklist).

management/commands/recompute_scores.py.

Docs: docs/05-scoring-engine.md with formula tables and worked examples, docs/06-instalment-engine.md.

Merge: feat(scoring): add explainable 8-factor client health score and 5-verdict instalment engine with full test coverage

Phase 3 — API layer (1 weekend)
api/clients.py, api/invoices.py, api/payments.py, api/plans.py, api/dashboard.py, api/insights.py, api/events.py, api/targets.py, api/fx.py, api/calendar.py.

Every endpoint returns view-shaped data (one call per screen).

Auto-generated /api/openapi.json.

frontend: npm run gen:api generates src/api/schema.ts.

Docs: docs/07-api.md with endpoint reference.

Merge: feat(api): expose typed Ninja routers for every domain with view-shaped responses

Phase 4 — Design system + shell (1 weekend)
Tailwind config with all tokens from Part 3.

styles/globals.css with CSS custom properties.

shadcn/ui installed, every component re-themed to Terminal Ledger tokens. No default shadcn styling survives.

components/layout/Shell.tsx, Sidebar.tsx, Topbar.tsx, MobileNav.tsx.

Topbar widgets: live clock, calendar popover, FX converter, global search, user menu.

Sidebar target widget.

docs/08-design-system.md with a live style guide page (dev-only route /dev/tokens).

Merge: feat(ui): establish Terminal Ledger design system and app shell with persistent clock, calendar, FX, and target widgets

Phase 5 — Landing page (1 weekend)
features/landing/LandingPage.tsx + sections.

Hero slideshow with 5 self-hosted Unsplash photos, crossfade 1200ms, pause on hover, reduced-motion fallback.

Translucent overlay per spec (backdrop-filter: blur(20px) saturate(140%)).

Smooth scroll, Framer Motion whileInView reveals.

Feature grid, "who it's for", "the system", audit trail section, CTA, footer.

Docs: docs/09-landing.md.

Merge: feat(landing): add translucent hero slideshow with real imagery and smooth-scroll feature sections

Phase 6 — Auth + onboarding (half weekend)
Django session login.

features/auth/LoginPage.tsx, RequireAuth.tsx.

CSRF handling via cookie + credentials: 'include'.

First-run onboarding modal: currency, base country, target.

Merge: feat(auth): add session login with CSRF-safe requests and first-run onboarding

Phase 7 — Dashboard (1 weekend)
Full dashboard grid per spec.

Every chart built as React.memo + useMemo on data and options.

All charts fill their cards completely.

KPI sparklines.

Today panel (instalments due, invoices crossed due, ghosted clients).

Merge: feat(dashboard): build 12-column dashboard with full-bleed charts, sparklines, and today panel

Phase 8 — Clients module (1 weekend)
Clients list with filter/search/sort.

Client detail page per spec.

Client form (create / edit).

Score breakdown visualisation with all 8 factors + penalties.

Radar chart.

Red flag list.

Timeline component.

Merge: feat(clients): add filterable client list and full detail page with explainable score breakdown and timeline

Phase 9 — Invoices + payments (1 weekend)
Invoices list with status filters.

Invoice create/edit.

Payment modal with live FIFO allocation preview.

Invoice status reconciliation.

Merge: feat(invoices): add invoice lifecycle with payment modal and live FIFO allocation preview

Phase 10 — Instalment plans UI (1 weekend)
Plan editor modal (quick generator + manual rows + grace + deadline).

Plan block on client detail.

Plan dots on invoice rows.

Instalment-level payment shortcuts.

Merge: feat(plans): add instalment plan editor with quick generator, manual rows, and five-verdict tracking

Phase 11 — Insights + Avoid + History (1 weekend)
Insights page with plan outcomes, cashflow forecast, aging, concentration, cohort analysis.

Avoid page with red-bordered client cards and every red flag visible.

History page — full audit trail, filterable by client/event type/date, exportable.

Merge: feat(insights): add plan outcomes, avoid page with red-flag dossier, and full event audit trail

Phase 12 — Persistent widgets (1 weekend)
Target tracker: CRUD for targets, sidebar progress ring, dedicated target detail page with projection lines (on track / N days behind / projected to hit on X).

Calendar: month view with due-date dots, day detail popover, "today" button.

Clock: topbar HH:MM:SS update loop, timezone-aware.

Currency converter: topbar popover, live rates from FxRate table, auto-applied to multi-currency displays.

Merge: feat(widgets): add persistent clock, calendar, FX converter, and target tracker with projection visualisations

Phase 13 — PWA + mobile polish (half weekend)
vite-plugin-pwa configured (manifest + Workbox asset caching only, no API caching).

Install prompt flow.

Icons (192, 512, maskable).

Full mobile pass on every page: tab bar, card lists, full-screen sheets, minimum touch targets, minimum font sizes.

Merge: feat(pwa): add installable PWA with offline app shell and complete mobile-responsive pass on all routes

Phase 14 — Sounds + notifications (half weekend)
lib/sounds.ts — Web Audio synthesis for all 5 sound presets.

Sound toggle per category in Settings.

Browser Notification API integration with permission flow.

Wiring: payment recorded, plan verdict flips, invoice overdue, instalment due.

Merge: feat(sounds): add Web Audio notification tones, per-category toggles, and browser notifications for plan verdict and overdue events

Phase 15 — Documentation + final polish (1 weekend)
README finalized with flow diagrams (Excalidraw exports → docs/diagrams/).

Full docs/ folder complete: every feature has its own file.

Every module has a docstring.

Every custom component in frontend/src/components/ documented in docs/15-components.md.

Error boundaries, loading skeletons, empty states everywhere.

Performance pass: bundle analysis, chart memoization audit, image optimization (hero images served as WebP via Vite's ?format=webp or vite-imagetools).

Accessibility pass: keyboard nav, focus order, ARIA labels, contrast audit.

Merge: docs: complete feature documentation, add flow diagrams, and finalize README

PART 6 — VERSION CONTROL WORKFLOW
Branches
Two branches only, forever:

main — always deployable. Every commit on main runs the app. No exceptions. If main breaks, fixing it is the highest priority.

perez — the feature/integration branch. Every phase of work happens on perez. Never commit directly to main.

No develop, no release/*, no hotfix/*, no long-lived feature branches. One feature branch. When a phase is complete, green, and documented, perez is fast-forward-merged into main (or squash-merged if the phase was messy — see below).

Workflow per phase
Start of phase: git checkout perez && git pull origin main — bring perez up to date with main before starting.

Work in small, meaningful commits (see conventions below). Each commit compiles. Each commit passes the manual smoke test.

End of phase:

Run pytest — all green.

Run npm run build — no TS errors, no build warnings.

Manual smoke test on desktop and mobile (Chrome DevTools device mode is sufficient — iPhone 12 and Pixel 5 presets).

Open the app, click through every changed route, verify no console errors.

Update the corresponding docs/NN-feature.md.

Merge to main: git checkout main && git merge perez --no-ff -m "merge: phase N — <phase name>" — a merge commit is required (no fast-forward), so main history shows a clear phase boundary.

Tag: git tag -a v0.N.0 -m "Phase N — <phase name>" and push tags.

Post-merge: git checkout perez && git merge main to keep perez current.

Commit message conventions
Format: Conventional Commits, scoped, imperative mood, ≤72 chars in the subject line, detailed body when needed.

text
<type>(<scope>): <short summary>

<body — optional, wrapped at 72 chars>

<footer — optional: refs, breaking changes>
Types:

feat — new feature

fix — bug fix

refactor — code change that neither fixes a bug nor adds a feature

perf — performance improvement

style — formatting, whitespace, tokens (not CSS features)

docs — documentation only

test — adding or fixing tests

chore — build tooling, dependencies, config

merge — merge commits

Scopes (fixed list):
models, scoring, instalments, api, ui, landing, dashboard, clients, invoices, plans, insights, avoid, history, settings, pwa, sounds, widgets, docs, bootstrap, auth, db

Rules:

Subject in imperative present tense: "add", "fix", "remove", "refactor". Not "added", "adds", "adding".

No period at the end of the subject line.

Body (if present) explains what and why, not how. The diff shows how.

Reference the phase in the footer when relevant: Phase: 7.

No commit message may ever be "update", "fixes", "changes", "wip", "stuff", or a single word.

Examples:

text
feat(plans): add five-verdict instalment engine with FIFO allocation

Introduces a pure-functional verdict engine that computes one of:
perfect, late, in_progress, at_risk, broken. Allocation is FIFO
across scheduled instalments with overflow-to-earliest behaviour.

Emits plan_perfect, plan_late, or plan_broken signals on verdict
transitions so the scoring engine and event log stay in sync.

Phase: 2
text
fix(scoring): weight payment lateness by invoice amount

Previously the average days-late was a simple mean across settled
invoices. A single $50 invoice paid 90 days late skewed a client
with $50,000 of on-time payment. Now weighted by invoice amount.

Phase: 2
text
style(ui): replace default shadcn blue with Terminal Ledger primary

All interactive states now use --primary (#58A6FF) instead of the
shadcn default. Buttons, focus rings, links, active nav items, and
info badges are the only places this colour appears.

Phase: 4
"Green before merge" checklist
Every phase, before merging to main, all of these must be true:

□ pytest passes (backend).
□ npm run build passes with zero TS errors (frontend).
□ npm run lint passes with zero warnings (backend ruff + frontend eslint).
□ No console.log anywhere in the frontend (search and remove).
□ No TODO/FIXME left in new code unless tracked in a docs/16-backlog.md entry.
□ Every changed route works on 1440px desktop and 375px mobile.
□ No colour outside the token system (grep -r "#[0-9a-fA-F]\{6\}" frontend/src returns nothing outside globals.css).
□ Docs for the phase have been written (docs/NN-phase.md).
□ Demo seed still produces a working app (python manage.py reset_demo && python manage.py seed_demo).
□ Manual smoke test: log in → dashboard loads with charts → open client → record payment → verify score updates → check timeline shows the new event.
If any box is unchecked, main does not receive the merge.

Merge discipline
Never force-push to main. Ever.

Never rebase perez onto main after commits have been merged. Use merge commits.

Squash only if a phase has many trivial commits (e.g. "fix typo", "actually fix typo"). Default is a merge commit.

Merge commit message format: merge: phase N — <phase name>.

Delete nothing from history. No git commit --amend on pushed commits. Fix forward.

No CI
Per the requirement, no GitHub Actions, no GitLab CI, no external runner. The main branch's correctness is enforced by human discipline + the checklist above. This is acceptable for a single-developer private tool. If this ever becomes a team project, this decision is revisited.

PART 7 — DOCUMENTATION STANDARDS
Every feature, every phase, every non-obvious decision gets a file in docs/.

Required docs files
File	Contents
docs/00-master-spec.md	This document. Canonical source of truth.
docs/01-setup.md	Local dev setup, Docker, environment variables, first run
docs/02-architecture.md	System diagram, data flow, why Django + React, module boundaries
docs/03-data-model.md	Every table, every column, every relationship, ER diagram
docs/04-seeding.md	How the demo seed works, how to reset
docs/05-scoring-engine.md	Formula tables, tier thresholds, worked examples, factor rationale
docs/06-instalment-engine.md	FIFO allocation algorithm, verdict state machine, grace periods
docs/07-api.md	Full endpoint reference, request/response shapes, error codes
docs/08-design-system.md	Every token, every component, live examples
docs/09-landing.md	Hero slideshow behaviour, overlay stack, imagery sourcing
docs/10-auth.md	Session auth, CSRF, login flow, first-run onboarding
docs/11-dashboard.md	Grid layout, chart memoization rules, polling cadence
docs/12-clients.md	Filters, client detail sections, score breakdown rendering
docs/13-invoices.md	Status reconciliation, payment modal, FIFO preview mirror
docs/14-plans.md	Plan editor UX, five verdicts, dots and blocks
docs/15-widgets.md	Clock, calendar, FX converter, target tracker — behaviour and DB sources
docs/16-pwa.md	Manifest, service worker caching strategy, install flow, mobile pass notes
docs/17-sounds.md	Web Audio synthesis, sound presets, notification API integration
docs/18-version-control.md	Branch model, commit conventions, merge checklist (mirrors Part 6)
docs/19-backlog.md	Known deferrals, TODOs, future ideas
docs/20-troubleshooting.md	Common issues: DB locked, migrations out of sync, PWA cache stale
Rules for every doc
Opens with a one-paragraph summary of what the feature is and why it exists.

A diagram where the feature has any flow (Excalidraw exports as .png in docs/diagrams/).

Every code snippet is copy-paste runnable.

Every doc ends with a ## Changelog section — dated list of what changed in this feature.

README.md (root)
The README is the front door. It is not a marketing page. It is an operator's manual.

markdown
# KC Ledger

Private financial operations console for a solo freelance developer.

Tracks every dollar, every instalment, every client signal — and tells
you who's worth keeping.

---

## What it does

- **Dashboard** — live KPIs, cashflow, aging, plan outcomes
- **Client health** — explainable 0–100 score across 8 factors + penalties
- **Instalment plans** — five-verdict tracking (Perfect / Late / In progress / At risk / Broken)
- **Avoid page** — every red-flagged client with a full dossier of reasons
- **Audit trail** — every event, every payment, every verdict flip, forever
- **Persistent widgets** — clock, calendar, FX converter, target tracker
- **PWA** — installable on phone and desktop, works offline for the app shell

---

## Stack

| Layer | Choice |
|-------|--------|
| Backend | Django 5 + Django Ninja |
| Database | SQLite (WAL) |
| Frontend | React 18 + TypeScript + Vite |
| State | TanStack Query v5 |
| Charts | Chart.js 4 |
| Design | Terminal Ledger (dark, dense, mono-accented) |
| Deploy | Docker Compose + nginx |

---

## Architecture

\`\`\`
Browser / PWA
  │
  │  JSON over HTTP
  ▼
Django + Ninja  ──  Services (scoring, instalments, fx, targets)
  │
  ▼
SQLite (WAL)   ──  data/ledger.db
\`\`\`

*(Full diagrams in `docs/diagrams/`.)*

---

## Data flow

\`\`\`
Client / Invoice / Plan → Event log → Scoring engine → Dashboard
                              ▲
                    Payments ─┘ (FIFO allocation)
\`\`\`

---

## Quick start

\`\`\`bash
git clone <repo> kc-ledger && cd kc-ledger
cp .env.example .env
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo
open http://localhost:8000
\`\`\`

Default credentials: set in `.env` on first run.

---

## Development

\`\`\`bash
# Backend
docker compose exec web python manage.py runserver 0.0.0.0:8000

# Frontend
cd frontend && npm install && npm run dev
# → http://localhost:5173 (proxies /api → :8000)
\`\`\`

---

## Version control

Two branches: `main` (always deployable) and `perez` (feature branch).
Every phase is developed on `perez`, then merged to `main` with a merge
commit after the green checklist passes.

See [`docs/18-version-control.md`](docs/18-version-control.md).

---

## Documentation

Every feature has a doc. Start at [`docs/00-master-spec.md`](docs/00-master-spec.md).

---

## Backup

\`\`\`bash
cp data/ledger.db data/backups/ledger-$(date +%F).db
\`\`\`

Do this weekly. Or wire it into a cron job. Do not lose this database.

---

## License

Private. Not for redistribution.
PART 8 — THE MASTER BUILD PROMPT
The following is the exact prompt to feed to a coding model or a human developer to build this system from scratch. It assumes the entire spec above.

You are building KC Ledger — a private financial operations console for a solo freelance developer. The full specification lives in docs/00-master-spec.md (this document). Read it before writing a single line of code.

Non-negotiable rules
Stack is locked: Django 5 + Django Ninja + SQLite (WAL) on the backend. React 18 + TypeScript + Vite + TanStack Query v5 + React Hook Form + Zod + shadcn/ui + Chart.js + Framer Motion + vite-plugin-pwa on the frontend. No alternatives considered.

Design system is locked to "Terminal Ledger" — all tokens in Part 3 of the spec. No hardcoded colours, spacing, or fonts anywhere outside globals.css. No exceptions. Before any commit, grep -r '#[0-9a-fA-F]\{6\}' frontend/src must return only globals.css.

This is NOT an AI-generated SaaS site. Read the DO/DON'T list in Part 3 and the "Landing page restrictions" in Part 4 twice. No purple gradients, no bouncy animations, no floating cards over abstract blobs, no default shadcn styling, no generic Lucide icons used unmodified, no emoji in the UI, no "supercharge/elevate/seamless" copy. When in doubt: dense, dark, precise, audited.

Every number on screen comes from the DB via the API. No hardcoded demo data in React. If the DB is empty, show a proper empty state.

Every route fetches once. One endpoint per screen. GET /api/clients/{id} returns score, breakdown, invoices, payments, plans, timeline, red flags — all of it. No N+1 over HTTP.

The event log is append-only. Every meaningful action writes an immutable events row. Soft deletes only.

The scoring engine is pure. No ORM writes inside scoring functions. Given a snapshot, it returns a deterministic result. This is what makes it testable and trustworthy.

Every chart fills its card. <canvas> receives width: 100%; height: 100%. Cards have fixed height. No letterboxing, no wasted space.

Every chart is memoized. React.memo + useMemo on both data and options. This is not optional.

Mobile-first verification. Every screen must be checked on 375×667 (iPhone SE) AND 1440×900 (desktop) before the phase is considered complete. Both must feel native.

Build phases
Follow Part 5 of the spec exactly. Phase 0 through Phase 15. Do not skip ahead. Each phase ends with a green merge to main.

Branch workflow (strict)
main is always deployable. Never commit directly to main.

perez is the only feature branch. All work happens there.

At the end of each phase: pytest passes, npm run build passes, manual smoke test on desktop + mobile passes, corresponding doc written, then git checkout main && git merge perez --no-ff -m "merge: phase N — <phase name>".

Tag each merge: git tag -a v0.N.0 -m "Phase N — <phase name>".

No CI workflows. The green checklist in Part 6 is what enforces correctness.

Commit discipline
Conventional Commits. Format in Part 6. Imperative mood, ≤72 char subject, explanatory body when the change isn't obvious from the diff. Never commit messages like "update", "fix stuff", "wip", "changes". Every commit compiles and runs.

Documentation
Every phase adds a file to docs/. Every non-obvious decision gets a paragraph. Diagrams (Excalidraw exports) go in docs/diagrams/. The master README is written in Phase 0 and updated at the end of every phase — it is the operator's manual, not a sales page.

The essential non-negotiable UI moments
Landing hero: full-bleed real photography (5 Unsplash images, self-hosted in frontend/src/assets/hero/), rotating every 8s with 1200ms crossfade, pause on hover, backdrop-filter: blur(20px) saturate(140%) overlay with rgba(11,15,20,0.62) backdrop and rgba(11,15,20,0.35) content panel. Reduced-motion users see the first image only, no rotation.

Dashboard: 12-column grid, no wasted vertical space, all 5 charts visible in one viewport at 1440×900.

Client detail: score breakdown shows every factor with its point contribution and a plain-English detail sentence — no black box.

Instalment plans: the five-verdict pill (Perfect/Late/In progress/At risk/Broken) is the visual centrepiece of the plan block. Payment modal previews FIFO allocation live as you type.

Avoid page: each client card has a red left border (3px) and lists every red flag with a real sentence. Dossier export as PDF.

Topbar: live clock ticking every second, calendar popover with due-date dots, FX converter, target progress ring in the sidebar — all persisted across every route.

What "done" means
You open the app on a laptop, and:

The landing page loads in under 1 second with a rotating hero and real imagery.

You sign in, and the dashboard loads with 6 KPIs, 5 charts, a today panel, and a client health list — all from live DB data.

You click a client and immediately see a health score with a readable breakdown, every invoice, every payment, every event in their history, and their current instalment plan with a verdict.

You record a payment, and — without a refresh — the client's score, the dashboard totals, the plan verdict, and the topbar target ring all update.

You pull out your phone, open the app (installed to home screen), and every page works. The calendar fits. The tables become cards. The charts fill their space. Touch targets are 44px. Fonts are legible.

You log an overdue instalment via the admin, and within 60 seconds the app fires the alarm sound and a toast saying "Plan flipped to broken — INV-4001."

Ship it in phases. Do not build the whole thing at once. Every phase ends with a merge to main and a tag. Every phase has its doc. Every phase is green before it merges.

Start with Phase 0. Go.

END OF MASTER SPECIFICATION
text

**What to do with this document:**

1. Save as `docs/00-master-spec.md` in the new repo.
2. Read Part 3 (Design System) and Part 4 (Landing + UI) once more before writing any CSS — those are the parts that determine whether this looks like a professional tool or an AI-generated site.
3. Follow Part 5 (Phases) strictly. Merge to `main` at the end of each phase, tag it, move on.
4. If you want to start building now, the immediate next step is **Phase 0** — scaffold the repo, drop this file into `docs/`, commit it as the very first commit: `docs: add master specification (v1.0)`.