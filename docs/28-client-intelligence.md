# KC Ledger — local-first client intelligence engine

**Primary system:** internal Django/Decimal ledger and pure eight-factor score; evidence-derived client pattern analysis and owner-reviewable warnings. **Secondary:** optional per-request Gemini or xAI Grok advisory. No model is required for any local scoring, risk review, charts or comparisons.

## Evidence and matching, not profiling people

The engine uses only *recorded business interactions*:
- manually coded behaviour events: payment delays, scope changes, abusive messages, chargebacks, rate renegotiation, late feedback, missed meetings, revision overages, missed deadlines, ghosting records and contract disputes
- objective invoice state: open overdue, disputed, written off
- objective payment lateness against its invoice due date
- positive signals: timely payments, clear approvals, scope adherence, accepted increases, repeat engagements

**Explicitly excluded:** name and company text, nationality/location, email/phone, demographic or protected characteristics, personality judgments, inferred mental traits, website/social content or AI-generated accusations. Events are append-only; corrections require a new factual event and owner review. A record marked blacklisted is an explicit owner's status, not a model prediction.

Each client has a rebuildable `ClientIntelligenceProfile` (signal counts, factual metrics, score snapshot), a daily `ClientIntelligenceObservation` (genuine score/risk history), and `ClientPatternAlert` rows (reference client, signal overlap, review status). An optional `ClientAdvisoryReport` stores a model's answer separately from primary facts.

### How risk is computed

The existing eight-factor 0–100 health score remains the authoritative *client health* index, using ledger payments, invoicing, delivery and relationship history. The new separate **risk review index** (0–100) combines capped, severity-weighted negative evidence and low health; it is a triage indicator, *not the probability that someone will behave badly*.

**Confidence by sample size:** 0–2 observations = insufficient; 3–7 limited; 8–19 moderate; 20+ established. Low confidence is prominent. An absent event is not positive proof that the client is safe.

**Historical match:** current client must share **at least two distinct adverse event types** with an older client and a **weighted Jaccard overlap of at least 55%**. The historical reference must have at least a mild review index or be explicitly blacklisted. Matching signals and their counts are displayed on an actionable warning. The engine never assumes a new client is the old client or has the old client's character.

An owner can mark alerts **reviewed** or **dismissed**, while retaining the evidence and review trail. A materially new pattern can reopen a previous dismissal. Refreshing unchanged records does not fabricate additional events.

### Audit and refresh model

- Recording an observable signal in the Client Intelligence page appends an immutable Event, recalculates the primary eight-factor score and refreshes all cross-client comparisons in one DB transaction.
- A single on-prem scheduler refreshes intelligence every 20 minutes; the protected Vercel Cron performs its refresh with its scheduled ledger tasks.
- Daily overdue reminders, ghosting alerts, and newly drafted recurring invoices refresh affected clients' stored health scores, so time-sensitive indicators do not remain stale until the owner makes a financial edit.
- Opening the portfolio/client intelligence endpoints refreshes only derived projections and the daily observation snapshot. It does not mutate invoices, payments or the official owner classification.
- Archived/soft-deleted clients remain available as historical references but no longer appear as current prospects. There is no automatic deletion or person matching based on PII.
- Initial event, invoice and payment metrics are aggregated in SQL; per-client profile and match rows are indexed and idempotent.
- Full audit history is preserved by source Event rows. Original financial tables continue to use PostgreSQL primary or a **pinned, independent SQLite fallback**; switching backends does not silently synchronize records.

## UI and data visualizations

Open **Intelligence** from the main navigation. The page groups analytics to prevent one giant landing page:

| Portfolio | Pattern watch | Individual client |
| --- | --- | --- |
| Health score distribution bar | 90-day average score/risk line | Score/risk daily timeline |
| Risk review doughnut | Client status polar chart | Warning radar chart |
| Signal frequency horizontal bars | Evidence heatmap, top 20 | Positive/adverse event counts |
| Score vs risk scatter | Reviewable shared-history alerts | Rule-based next steps |
| Filterable client register | Match explanations and status controls | Signal recording, optional Gemini/Grok, advice history |

Charts show actual stored observations, not synthetic/demo predictions. New deployments with no meaningful data display empty states; missing evidence is not fabricated.

## Local advisory: always usable, no API key

`POST /api/intelligence/advice` with `provider: "local"` returns the code-based recommendations and current evidence counts. This works offline on desktop and without external AI subscriptions.

## Gemini (optional)

1. Obtain a Gemini Developer API key from Google AI Studio. Consult Google's published free-tier model eligibility and quota in your account; free access is subject to change.
2. Set `LEDGER_AI_ADVICE_ENABLED=1` and `GEMINI_API_KEY=<secret>` in the backend's private environment. `LEDGER_GEMINI_MODEL=gemini-2.5-flash-lite` is the initial configurable default; if Google changes availability, set a currently supported model explicitly.
3. On a client dossier, choose Gemini, check **Send anonymous indicators for this request**, then request advice. The provider returns recommendations only; it **cannot** create events, approve invoices or modify scores.
4. If the provider rate limits, is unavailable or fails validation, local analysis remains in full operation. Never place the API key in the React bundle or client browser storage.

## xAI Grok (optional, metered)

xAI's public API is priced per token. Do **not** assume Grok API access is free because the Grok web UI or playground is available. To enable: set `XAI_API_KEY`, `LEDGER_AI_ADVICE_ENABLED=1`, and **`LEDGER_ENABLE_METERED_GROK=1`** to explicitly authorize potential costs. Default model `grok-4.3`, configurable in the private backend. The same per-request opt-in, sanitized input, response validation, throttling, no-autonomy and audit rules apply.

## Privacy boundary and model safety

The only outbound model context is *anonymous machine-produced codes and counts*, the selected client's numeric health score, risk index, confidence, invoice state counts and anonymous historical overlap scores. Never send client names, notes, email, phone, legal documents, raw event details, invoices, invoice totals or authentication data. The UI requires explicit user consent for **each** external model request. The backend uses fixed HTTPS endpoints, short timeouts, capped response sizes and validated JSON output; the provider never chooses arbitrary URLs. Responses are advisory and stored separately as owner-requested `ClientAdvisoryReport` rows.

The provider request is subject to your provider's data processing terms. If you prefer no off-device transfer, leave external AI disabled and use the local engine only. Model content can hallucinate or be outdated. Always verify factual advice and avoid discriminatory, unlawful or unwarranted financial/contract decisions.

## Endpoints

All are staff-session authenticated and CSRF-protected for mutations:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/intelligence/overview` | Portfolio metrics, charts, heatmap, current alerts |
| `GET /api/intelligence/clients/{id}` | Client evidence, history, profile, local advice, matches and advice history |
| `GET /api/intelligence/signal-types` | Fixed observable-signal vocabulary |
| `POST /api/intelligence/clients/{id}/signals` | Record an immutable factual signal, refresh score and matches |
| `POST /api/intelligence/alerts/{id}/review` | Review or dismiss an alert |
| `POST /api/intelligence/advice` | Primary local or opt-in external advisory |

No API accepts a model-generated classification as an update to a client or ledger record.

## Production acceptance gates

- Migrate to new `ClientIntelligenceProfile`, `ClientPatternAlert`, `ClientIntelligenceObservation`, `ClientAdvisoryReport` tables on **both** PostgreSQL and SQLite fixtures; `makemigrations --check --dry-run` must pass.
- Verify no fabricated matches with only one common signal, matching behaviour counts with previously archived clients, review persistence, update idempotency, and inability to read private endpoints without staff session.
- Test documented adverse patterns in a synthetic example; verify each warning cites actual recorded signal codes.
- Reconcile existing eight-factor scores, money and invoice totals before and after migration. New profile tables do not alter financial source data.
- Test readable/no-data dashboards, narrow screens, keyboard access and performance with hundreds of clients.
- Exercise model request with consent denied and disabled provider; verify **zero outbound traffic**. With a test key, verify error handling, quota, privacy payload and cost caps.
- Deploy/upgrade and restore on a copy of a populated local PostgreSQL database, and clean Windows devices; verified source CI alone cannot guarantee actual user-machine operation.
- Review whether owner classification and retained client notes meet applicable data-protection obligations, define retention/erasure policy for sensitive data and provide access controls.

**Google ADK decision:** not included. KC Ledger currently uses single-turn, read-only, strict-schema model advisories; Google ADK is useful for complex tool-based multi-agent orchestration but unnecessary and less auditable here. Reevaluate only when a specific audited multi-step agent workflow is required.

Updated 2026-11-21.
