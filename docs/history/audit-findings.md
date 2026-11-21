# KC Ledger — cross-layer deep-audit log (November 21, 2026)

| Layer | Finding | Implementation and verification gate |
| --- | --- | --- |
| Scoring | Eight deterministic factors and existing PDF/client scores work, but no explicit structured behaviour recording/temporal match engine | New immutable signal API, SQL-derived profile, risk index, history, historical match alert |
| New clients | Previously shared names/countries alone could not trigger matching; no reliable pattern API existed | At least two corroborated event kinds, severity-weighted overlap >=55%, older adverse reference required |
| Owner control | Scores below 40 previously **blocked invoice creation automatically** | Maintain explicit owner blacklist control; otherwise show caution warning instead of autonomous rejection |
| Historical data | Client deletions are soft, so historical conduct should be usable as reference | Read past records via all_objects for intelligence comparisons; do not reactivate archived clients |
| Database | PostgreSQL primary, pinned SQLite fallback and transactional ledger are in place | Add four indexed derived-intelligence tables + migrations, test both engines |
| API | Staff/Ninja auth and CSRF exist; no intelligence API or consent boundary | New protected router with bounded input, review actions, deterministic local and explicit external advice |
| External AI | No current provider code; free access to Grok must not be assumed | Fixed Gemini/Grok adapters, server-only keys, strict opt-in, disabled paid Grok by default, errors isolated |
| Frontend | Dashboard and insights had charts, but no dedicated evidence intelligence workspace | Portfolio charts, heatmap, scatter, timelines, per-client radar and pattern-watch panels |
| Background | Existing scheduler refreshes ledger-derived events and FX | Periodic intelligence regeneration and Vercel daily job, no external model calls in scheduler |
| Correctness | AI model cannot verify a client character, source data accuracy or legal claims | Explicit confidence levels, observed-evidence labels, human review, no auto-status changes |
| Operations | New tables and model calls need real environment acceptance | SQLite/Postgres/backend, frontend, Docker, Chromium and Windows CI plus real key/restore/device drills |

No software-only test proves **100% correctness**. The acceptance gate is a passing suite at the current merged commit plus actual production backup/restore, network, external model and device checks. No data should be inferred from unspecified source records; manually entered flags require traceable factual evidence. 

Updated 2026-11-21.
