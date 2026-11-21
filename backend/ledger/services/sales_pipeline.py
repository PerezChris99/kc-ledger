"""Factual lead/proposal tracking for a single-owner business.

Observed wins and losses are not causal effects, quoted amounts are not cash,
and sparse historical win rates are not calibrated predictions.
"""

from collections import Counter
from datetime import timedelta

from django.utils import timezone

from ledger.models import BusinessOpportunity

OPEN_STAGES = (
    BusinessOpportunity.Stage.DISCOVERED,
    BusinessOpportunity.Stage.CONTACTED,
    BusinessOpportunity.Stage.QUALIFIED,
    BusinessOpportunity.Stage.PROPOSED,
    BusinessOpportunity.Stage.NEGOTIATING,
)
DISPLAY_STAGES = (
    *OPEN_STAGES,
    BusinessOpportunity.Stage.WON,
    BusinessOpportunity.Stage.LOST,
)


def pipeline_overview(today=None):
    today = today or timezone.localdate()
    counts = Counter()
    sources = {}
    stale = 0
    quoted_by_currency = Counter()
    rows = []
    won = lost = 0
    for opportunity in (
        BusinessOpportunity.objects.order_by("-updated_at", "-id")
        .values(
            "id",
            "name",
            "client_id",
            "source",
            "stage",
            "proposed_amount",
            "currency",
            "opened_on",
            "closed_on",
            "next_action",
            "lost_reason",
            "updated_at",
        )
        .iterator(chunk_size=250)
    ):
        stage = opportunity["stage"]
        if stage != BusinessOpportunity.Stage.ARCHIVED:
            counts[stage] += 1
        pair = sources.setdefault(opportunity["source"], {"won": 0, "lost": 0}) if stage != BusinessOpportunity.Stage.ARCHIVED else None
        if stage == BusinessOpportunity.Stage.WON:
            won += 1
            pair["won"] += 1
        elif stage == BusinessOpportunity.Stage.LOST:
            lost += 1
            pair["lost"] += 1
        if stage in OPEN_STAGES:
            quoted_by_currency[opportunity["currency"]] += opportunity["proposed_amount"]
            if today - opportunity["updated_at"].date() >= timedelta(days=21):
                stale += 1
        if len(rows) < 80:
            rows.append(
                {
                    "id": opportunity["id"],
                    "name": opportunity["name"],
                    "client_id": opportunity["client_id"],
                    "source": opportunity["source"],
                    "stage": stage,
                    "proposed_amount": str(opportunity["proposed_amount"]),
                    "currency": opportunity["currency"],
                    "opened_on": opportunity["opened_on"].isoformat(),
                    "closed_on": (
                        opportunity["closed_on"].isoformat() if opportunity["closed_on"] else None
                    ),
                    "next_action": opportunity["next_action"],
                    "lost_reason": opportunity["lost_reason"],
                    "updated_at": opportunity["updated_at"].isoformat(),
                }
            )
    completed = won + lost
    # Only report descriptive rate once there are enough CLOSED outcomes.
    # This does not predict any single lead's buying probability.
    win_rate = round(100 * won / completed, 1) if completed >= 5 else None
    findings = []
    if stale:
        findings.append(
            {
                "id": "stale_sales_pipeline",
                "priority": "medium",
                "title": "Active sales opportunities lack recent recorded progress",
                "evidence": f"{stale} open opportunity record(s) have not changed for 21 days.",
                "action": "Confirm next action with each prospect and record the actual outcome.",
                "avoid": "Do not assume stale quotes are won revenue or guaranteed payments.",
                "confidence": "observed",
                "source": "Recorded opportunity dates; no external market data",
            }
        )
    if completed >= 5 and win_rate is not None and win_rate < 30:
        findings.append(
            {
                "id": "weak_observed_conversion",
                "priority": "medium",
                "title": "Recorded proposal outcomes warrant a pitch review",
                "evidence": f"{won} wins and {lost} losses ({win_rate}% observed win share).",
                "action": "Compare proposal scope, price objections and source channels; test a clear alternative.",
                "avoid": "Do not treat past win share as a future conversion probability or causal proof.",
                "confidence": "limited",
                "source": "Recorded closed opportunities; selection bias possible",
            }
        )
    return {
        "stages": [{"stage": stage, "count": counts[stage]} for stage in DISPLAY_STAGES],
        "total_open": sum(counts[stage] for stage in OPEN_STAGES),
        "won": won,
        "lost": lost,
        "closed_sample": completed,
        "observed_win_share_pct": win_rate,
        "conversion_evidence": "limited" if completed >= 5 else "insufficient",
        "stale_open_count": stale,
        "quoted_open_by_currency": [
            {"currency": key, "quoted_amount": str(value)}
            for key, value in sorted(quoted_by_currency.items())
        ],
        "sources": [
            {
                "source": source,
                "won": pair["won"],
                "lost": pair["lost"],
                "closed_sample": pair["won"] + pair["lost"],
            }
            for source, pair in sorted(sources.items())
        ],
        "opportunities": rows,
        "recommendations": findings,
        "limitations": (
            "Each stage is an owner-recorded business fact; this is not a sales forecast. "
            "Quoted amounts are not receivables, booked income or cash. "
            "Observed win share is shown only for at least five closed opportunities, "
            "and must not be presented as a buyer-specific probability."
        ),
    }
