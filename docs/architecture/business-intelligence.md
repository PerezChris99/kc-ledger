# KC Ledger — business-wide intelligence and decision system

The **Intelligence** workspace now defaults to **Business command**. The existing Client portfolio, Pattern watch and Client analysis remain separate tabs.

## The operating model

This is a local-first, explainable, rules-driven business co-pilot, not an autonomous AI agent. It combines the financial ledger, recorded project and client activity, chosen business objectives, and experiments to answer:

- **How are we doing?** Collected cash, recorded costs, net recorded cash, overdue exposure, invoice age, client count, work hours and project economics.
- **Where and why?** Monthly receipts and costs, recorded expense categories, client and project direct cash contribution, changes versus prior closed months, documentable collection issues and concentration risk.
- **What is changing?** Deterministic three-month median/MAD anomaly checks for completed months; no fake trends based on partial current months.
- **What comes next?** Low-confidence, historical median-based cash scenarios and explicit sensitivity analysis using pricing, collections and expense levers; no guaranteed sales, demand elasticity, probability estimates or cash-balance claims.
- **What should I do, and what should I avoid?** Rules that challenge high overdue exposure, overspending, dominant payer dependence, incomplete costs, inconsistent settlements and past decisions that did not improve their tracked metric.
- **Am I executing the right strategy?** Owner-written measurable objectives and strategy experiments, captured current baselines, review deadlines and eventual outcome notes. Before/after changes are observations, not proof of causation.
- **How should I approach a client?** Context-sensitive but non-manipulative discovery, scoping, deliverables, payment terms and proposal structure; uses only recorded engagements, outstanding balances and revision counts.
- **Can Gemini or Grok advise me?** Yes, as an optional, consent-gated **second opinion** based only on anonymous aggregate ratios, goal codes and strategy-outcome booleans. The deterministic rule engine and human owner remain primary.

No Google Agent Development Kit (ADK) is installed. These are bounded queries and a restricted model call, not a multi-agent task requiring autonomous execution.

## Correct accounting semantics

The primary equation is:

**Recorded net cash result = sum(recorded payments, converted to base currency) – sum(recorded expenses, converted to base currency).**

This is a historical recorded **cash performance proxy**, NOT net accounting profit, bank cash balance, tax profit, true operating cash flow or an audited income statement. An invoice does not become spendable cash until a payment is recorded. The ledger does not yet verify all owner salary, payroll, tax, depreciation, funding, capital expenditures, supplier obligations, refunds, capital, invoiced accrual recognition or completeness of expenses. Categorizing costs and recording all supplier/owner transactions is essential.

Historical cash receipts and attributable expenses remain included even when a client or engagement has been soft-archived. Archived clients are distinguished in economic history, excluded from active-client counts and excluded from the current pitch selector. This avoids creating a fictitious improvement in revenue or client concentration simply by archiving an account.

The engine *never* silently counts missing FX conversion as zero revenue; it identifies the missing currency. Financial goals become non-evaluable until conversion is complete. FX values currently use stored rates rather than historical per-transaction rates and should be treated accordingly. Project and client direct contribution excludes shared/unallocated cost and unrecorded labor, so it is NOT fully loaded profitability. Totals include direct client costs **and all business-wide unassigned expenses**. Any unrecorded item remains unknown—not invented.

### Financial views

- Monthly receipts vs recorded expenses (line)
- Monthly net recorded cash (positive/negative bar)
- Expense categories (doughnut)
- Client direct cash receipts vs costs (horizontal bar)
- Unpaid invoice age buckets (bar)
- Engagement receipts vs directly assigned costs (horizontal bar)
- Client financial table with receipts, costs, direct contribution, hours, overdue
- Trailing historical cash baseline and coarse scenario range (if sufficient evidence)

All use current, stored ledger data. Empty states are honest.

## Anomaly and scenario methods

A financial anomaly is emitted if a *completed* month's receipts or costs differ from the median of the prior 3 completed months by more than `max(30% of baseline, 3 × median absolute deviation)`, provided those months have financial activity. Changes are flagged for review, not treated as fraud or certainty.

Forecast readiness requires **at least three completed months containing recorded financial activity** within the trailing six completed months. The engine then uses a six-month median receipts and costs with a conservative deviation (median absolute deviation or at least 25%) to render an **illustrative** cash scenario. This is explicitly a historical sensitivity range, **not** a calibrated statistical prediction interval. It does not model seasonality, external economy, conversion probability, receivables collection guarantees or unrecorded costs.

**Sensitivity lab** lets you adjust illustrative effects of pricing, collections and cost levels. Percentages are assumed linear **solely for arithmetic**. No claim is made that raising prices really produces the stated receipts. Build actual lead and client conversion data before treating those levers as real forecasts.

## Latest audit corrections: evidence integrity and real sales outcomes

Previous versions could reclassify a reviewed strategy whenever live numbers changed, and marked a zero movement as favorable. Migration 0008 now stores the review timestamp, actual observed value, change, optional improvement verdict and evidence-quality reason. Owner reviews are closed snapshots: later live results remain visible separately, and closed reviews are not overwritten. Historical reviews from before this change remain **unmeasured** until a new experiment captures a genuine baseline.

Cash metrics now exclude future-dated payments, expenses, time entries and future-issued invoices from current totals. The report identifies excluded records. Missing conversions disable historical scenario/anomaly outputs, rather than implying precise data. The 30-day unpaid invoice schedule is **not** a guaranteed cash forecast, and 90-day receipts concentration complements lifetime concentration.

A small single-business opportunity pipeline (migration 0009) records lead source, factual stage, quoted amount, next action and actual won/lost outcome. A quote is never booked as revenue, invoice or payment. Won/closed descriptive percentage is displayed only after at least **five closed cases**; it is not an individualized conversion prediction. Neutral audited events record stage changes and corrections. The deterministic advisor can flag stale leads and poor documented conversion, with source/volume caveats.

See [scope-limited deep audit](../history/intelligence-pwa-audit.md).

## Goals, strategy experiments, and self-correction

`BusinessObjective` stores a name, details, one of six measurable metrics, a numeric target, deadline and status. Metrics: monthly receipts, monthly recorded cash result, maximum monthly expenses, maximum overdue unpaid balance, active clients, and collected receipts per logged hour.

`BusinessStrategyDecision` stores an owner-defined category, hypothesis/rationale, expected outcome, tracked metric, linked goal/client (optional), start and review date, status and owner outcome note. A strategy started **today** captures the current recorded metric baseline; a historical strategy **does not invent a past baseline**. On review it displays actual latest metric, observed delta and whether that delta moved in the intended direction, with an explicit caution that changes may be due to other factors. Owners—not the model—mark actions reviewed or cancelled. All updates create a neutral append-only audit event.

Money-valued objectives and strategy baselines are pinned to the ledger base currency at creation. If you later change the base currency, comparisons stop and are marked unavailable rather than silently interpreting USD targets as UGX (or vice versa). Set a new correctly denominated target before resuming monetary progress evaluation.

The advisor evaluates recorded data and your stated goals together. Examples:

| Evidence | What it challenges | Recommended next step |
| --- | --- | --- |
| Recorded expenses greater than cash collected | Spending beyond recorded receipts | Review biggest cost categories and collection timing; avoid assuming invoices are cash |
| Significant overdue invoices | Extending credit without safeguards | Agree dated payment plans and payment milestones |
| Majority of receipts from one payer | Client concentration dependency | Develop qualified new accounts while servicing the existing key customer |
| Recorded costs are 80% or more of receipts | Limited recorded cash buffer | Inspect pricing, cost allocation and high-overhead engagements |
| 30-day goal deadline with unachieved metric | Target drifting | Revisit assumptions and controllable activities |
| Strategy review due and baseline captured | Endless tactic without measured outcome | Document effect, possible confounders, then keep, alter or stop |
| A reviewed decision's metric moved against its direction | Wrong path | Challenge the hypothesis, identify what actually changed, revise plan |

There is **no autonomous invoicing, pricing change, credit decision, client rejection or spending commitment.** Confidence is limited by the data provided.

## Goal-aware ranked strategy experiments

The local advisor also ranks up to five **possible experiments** using an explainable heuristic: the urgency of actual rule findings, overlap with your active measurable goals, and directional observations from completed past experiments. It can prioritize collections discipline, cost containment, client diversification, price/scope management and data-quality repair. Each recommendation identifies the rules and goals behind it, practical test steps, implementation risk, and whether similar past experiments moved the chosen metric favorably or unfavorably. This is **not a trained optimization model** or proof of cause; it is a disciplined review order that you control.

## Client pitch guide

`GET /api/intelligence/business/pitch/{client_id}` builds a **safe structured proposal outline** using only internal business signals:
- overdue exposure: address collection before adding new unsecured delivery;
- recorded revision-limit exhaustion: clarify signed change requests;
- explicit owner blacklist: ask the owner to review the account before new work;
- otherwise: evidence-backed discovery → problem definition → deliverables and milestones → pricing → next step.

The guide does not infer personality, demographic traits, or buying probability and does not invent client testimonials. It is a repeatable baseline, not a finished persuasive pitch tailored to unseen client communications.

## API

All endpoints require the existing staff session; POST/PATCH operations enforce CSRF.

| Verb | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/intelligence/business/overview` | Reconcile business cash activity, KPIs, charts, anomaly reasons, goals and past decisions |
| GET | `/api/intelligence/business/scenario` | Hypothetical pricing, collections and cost sensitivity (bounded inputs) |
| GET | `/api/intelligence/business/pitch/{id}` | Evidence-based client proposal guidance |
| POST | `/api/intelligence/business/objectives` | Owner creates a measurable objective |
| PATCH | `/api/intelligence/business/objectives/{id}` | Pause, reactivate or mark goal complete |
| POST | `/api/intelligence/business/decisions` | Log a strategy and a baseline where recoverable |
| PATCH | `/api/intelligence/business/decisions/{id}` | Review/cancel an experiment with outcome note |
| POST | `/api/intelligence/business/advice` | Deterministic local or opt-in Gemini/Grok second opinion |

New PostgreSQL/SQLite tables are created by migration `0007_business_intelligence`: `BusinessObjective`, `BusinessStrategyDecision`, `BusinessAdvisoryReport`. The existing financial schema, ledger balances, client scoring and historical pattern tables remain unchanged.

## Proactive warnings

A local daily scheduler and protected Vercel daily cron evaluate high-priority business findings **without an LLM**. A stable rule identifier is emitted as an append-only event at most once every seven days, preventing repeated alarm noise. The existing authenticated notification-polling endpoint and optional system notification/sound UI surface these events. There are no warnings from an empty ledger and no automated financial/customer decisions. Stored warnings represent evidence at issuance; new ledger changes may resolve underlying conditions.

## External provider privacy

By default external providers are disabled. To use Gemini, configure `LEDGER_AI_ADVICE_ENABLED=1` and a valid private `GEMINI_API_KEY` on the server. xAI Grok requires `XAI_API_KEY`, `LEDGER_AI_ADVICE_ENABLED=1` and the explicit paid-use opt-in `LEDGER_ENABLE_METERED_GROK=1`; a free Grok web chat is **not** a free API entitlement. Availability and pricing change. No key is ever returned to the frontend.

The user must opt in for **each external advisory request**. The payload contains no client names, emails, notes, goals free text, raw financial amounts, invoices or project names. It contains sanitized counts, percentage ratios, coded goal directions, rule/anomaly identifiers and whether a previous tracked outcome moved favorably. Model responses are validated and saved as *separate advisory records*. They cannot write source facts, statuses, financial transactions or objectives.

## What is genuinely missing for a complete autonomous business brain

The system can only learn from **data actually present**. The present ledger is sufficient for rule-based internal finance and client strategy, but these capabilities require new sources, data quality and future development:

1. **Audited profitability:** bank reconciliation, a complete chart of accounts, taxes, owner compensation, liabilities, depreciation and proper accounting recognition.
2. **Predictive sales and pitching:** a CRM lead/opportunity pipeline with qualified leads, stages, pitch variants, deal outcomes, objections, customer acquisition cost, win/loss reason and channel attribution. There is no reliable per-client conversion probability without this.
3. **Market intelligence:** opted-in external industry/competitor/pricing feeds with timestamps and provenance. Internal receipts do **not** establish external trends.
4. **True strategy effect estimation:** controlled experiments or sufficiently rich longitudinal cohorts; before/after changes alone do not establish causation.
5. **Operating capacity:** staffing costs, available hours, project estimates, utilization, commitments and time allocation before giving reliable delivery/capacity optimization.
6. **Autonomy controls:** explicit owner approvals, change diffs, rollback semantics, hard spending limits and policy governance before any machine-initiated action.

**Production release acceptance** still requires full CI, database migration checks, Windows installer test, backup/restore on a populated production copy, multi-currency reconciliation, representative data and legal/privacy review. Passing source CI never guarantees every real-world case is correct.

Created 2026-11-21.
