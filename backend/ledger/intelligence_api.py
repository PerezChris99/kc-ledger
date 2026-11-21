"""Owner-only intelligence and optional, explicitly consented model advice."""

import json
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256

from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from ledger.models import (
    Client,
    ClientAdvisoryReport,
    ClientIntelligenceObservation,
    ClientPatternAlert,
    Event,
)
from ledger.services.advisory import (
    AdviceUnavailable,
    public_availability,
    request_advice,
)
from ledger.services.intelligence import (
    BEHAVIOUR_SIGNAL_CODES,
    NEGATIVE_SIGNALS,
    POSITIVE_SIGNALS,
    evidence_for_provider,
    local_recommendations,
    refresh_intelligence,
    read_intelligence,
)

router = Router(tags=["client-intelligence"])


class SignalIn(Schema):
    code: str
    detail: str = ""
    occurred_on: date | None = None


class AlertReviewIn(Schema):
    status: str
    note: str = ""


class AdviceIn(Schema):
    client_id: int
    provider: str = "local"
    share_anonymized: bool = False


def _get_client(client_id):
    try:
        return Client.objects.get(pk=client_id)
    except Client.DoesNotExist as exc:
        raise HttpError(404, "Client not found.") from exc


def _alerts_for_client(client):
    return list(
        ClientPatternAlert.objects.filter(client=client)
        .select_related("reference_client")
        .order_by("-similarity", "-created_at")[:30]
    )


def _alert_dict(alert):
    return {
        "id": alert.id,
        "client_id": alert.client_id,
        "reference_client_id": alert.reference_client_id,
        "reference_client": alert.reference_client.name,
        "similarity": alert.similarity,
        "shared_signals": alert.overlap,
        "status": alert.status,
        "review_note": alert.review_note,
        "updated_at": alert.updated_at.isoformat(),
        "explanation": (
            "Similar documented work events were recorded for another client. "
            "This is a review prompt, not a prediction or automatic rejection."
        ),
    }


@router.get("/signal-types")
def signal_types(request):
    rows = []
    for code, (label, severity, recommendation) in NEGATIVE_SIGNALS.items():
        if code not in BEHAVIOUR_SIGNAL_CODES:
            continue
        rows.append(
            {
                "code": code,
                "label": label,
                "severity": severity,
                "category": "warning",
                "recommended_action": recommendation,
            }
        )
    for code, label in POSITIVE_SIGNALS.items():
        rows.append({"code": code, "label": label, "severity": 0, "category": "positive"})
    return {"items": rows}


@router.get("/overview")
def overview(request):
    # This refreshes cached derived profiles and one observation per day, not
    # financial records or the user's judgments about individual clients.
    analyses = read_intelligence()
    clients = list(
        Client.objects.only("id", "name", "status", "score", "created_at").order_by("name", "id")
    )
    alerts = list(
        ClientPatternAlert.objects.filter(client_id__in=[c.id for c in clients])
        .select_related("client", "reference_client")
        .order_by("-similarity", "-updated_at")[:500]
    )
    open_alert_count = Counter(
        a.client_id for a in alerts if a.status == ClientPatternAlert.Status.OPEN
    )
    items = []
    buckets = Counter()
    behavior_frequency = Counter()
    risk_bands = Counter()
    for client in clients:
        data = analyses[client.id]["metrics"]
        for entry in data["adverse_signals"]:
            behavior_frequency[entry["kind"]] += entry["count"]
        bucket = (
            "85–100"
            if client.score >= 85
            else "70–84"
            if client.score >= 70
            else "55–69"
            if client.score >= 55
            else "40–54"
            if client.score >= 40
            else "0–39"
        )
        buckets[bucket] += 1
        risk_bands[
            "High review"
            if data["risk_index"] >= 65
            else "Watch"
            if data["risk_index"] >= 35
            else "Low evidence / low concern"
        ] += 1
        items.append(
            {
                "id": client.id,
                "name": client.name,
                "score": client.score,
                "status": client.status,
                "risk_index": data["risk_index"],
                "confidence": data["evidence_confidence"],
                "evidence_count": data["observations"],
                "issues": len(data["adverse_signals"]),
                "open_alerts": open_alert_count[client.id],
                "actions": data["actions"][:3],
            }
        )
    trend = list(
        ClientIntelligenceObservation.objects.filter(
            client_id__in=[c.id for c in clients],
            observed_on__gte=timezone.localdate() - timedelta(days=90),
        )
        .values("observed_on")
        .annotate(avg_score=Avg("score"), avg_risk=Avg("risk_index"), count=Count("client_id"))
        .order_by("observed_on")
    )
    return {
        "clients": items,
        "client_count": len(clients),
        "open_alert_count": sum(open_alert_count.values()),
        "status_distribution": [
            {"name": name, "count": count}
            for name, count in sorted(Counter(c.status for c in clients).items())
        ],
        "score_distribution": [
            {"bucket": name, "count": buckets[name]}
            for name in ("0–39", "40–54", "55–69", "70–84", "85–100")
        ],
        "risk_distribution": [
            {"name": name, "count": risk_bands[name]}
            for name in ("Low evidence / low concern", "Watch", "High review")
        ],
        "behavior_frequency": [
            {"kind": key, "label": NEGATIVE_SIGNALS[key][0], "count": count}
            for key, count in behavior_frequency.most_common(15)
        ],
        "score_risk": [
            {
                "id": row["id"],
                "name": row["name"],
                "score": row["score"],
                "risk": row["risk_index"],
                "evidence": row["evidence_count"],
            }
            for row in items
        ],
        "behavior_matrix": {
            "columns": [
                {"code": code, "label": NEGATIVE_SIGNALS[code][0]}
                for code, _ in behavior_frequency.most_common(10)
            ],
            "rows": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "counts": [
                        analyses[row["id"]]["signals"].get(code, 0)
                        for code, _ in behavior_frequency.most_common(10)
                    ],
                }
                for row in sorted(
                    items, key=lambda record: (-record["risk_index"], record["name"])
                )[:20]
            ],
        },
        "trend": [
            {
                "day": row["observed_on"].isoformat(),
                "avg_score": round(row["avg_score"], 1),
                "avg_risk": round(row["avg_risk"], 1),
                "clients": row["count"],
            }
            for row in trend
        ],
        "alerts": [_alert_dict(alert) for alert in alerts[:60]],
        "ai": public_availability(),
        "methodology": (
            "Deterministic client history, weighted recorded incidents and objective invoices. "
            "Similarity requires two shared negative event types and at least 55% weighted overlap. "
            "Scores and matching are advisory; neither automatically rejects clients."
        ),
    }


@router.get("/clients/{client_id}")
def intelligence_detail(request, client_id: int):
    client = _get_client(client_id)
    analyses = read_intelligence()
    summary = local_recommendations(client.id, analyses)
    alerts = _alerts_for_client(client)
    history = list(
        ClientIntelligenceObservation.objects.filter(client=client)
        .order_by("-observed_on")[:90]
        .values("observed_on", "score", "risk_index", "evidence_count")
    )
    reports = list(ClientAdvisoryReport.objects.filter(client=client).order_by("-created_at")[:20])
    return {
        "id": client.id,
        "name": client.name,
        "status": client.status,
        "score": client.score,
        "analysis": analyses[client.id]["metrics"],
        "recommendation": summary,
        "alerts": [_alert_dict(alert) for alert in alerts],
        "history": [
            {
                "date": row["observed_on"].isoformat(),
                "score": row["score"],
                "risk_index": row["risk_index"],
                "evidence_count": row["evidence_count"],
            }
            for row in reversed(history)
        ],
        "advisories": [
            {
                "id": report.id,
                "provider": report.provider,
                "model": report.model_name,
                "advice": report.advice,
                "created_at": report.created_at.isoformat(),
            }
            for report in reports
        ],
        "ai": public_availability(),
    }


@router.post("/clients/{client_id}/signals")
@transaction.atomic
def record_signal(request, client_id: int, payload: SignalIn):
    client = _get_client(client_id)
    allowed = set(BEHAVIOUR_SIGNAL_CODES) | set(POSITIVE_SIGNALS)
    if payload.code not in allowed:
        raise HttpError(422, "Use a documented, observable behaviour signal.")
    note = payload.detail.strip()
    if len(note) > 800:
        raise HttpError(422, "Evidence note cannot exceed 800 characters.")
    occurred_on = payload.occurred_on or timezone.localdate()
    if occurred_on > timezone.localdate() or occurred_on < timezone.localdate() - timedelta(
        days=3650
    ):
        raise HttpError(422, "Signal dates must be within the last ten years.")
    if payload.code in NEGATIVE_SIGNALS:
        label, weight, _ = NEGATIVE_SIGNALS[payload.code]
        polarity = -1
        category = (
            Event.Category.MONEY
            if payload.code in {"payment_late", "chargeback"}
            else Event.Category.COMMS
            if payload.code in {"abusive", "late_feedback", "missed_meeting", "ghosting_detected"}
            else Event.Category.BEHAVIOUR
        )
    else:
        label, weight = POSITIVE_SIGNALS[payload.code], 1
        polarity, category = 1, Event.Category.RELATIONSHIP
    Event.objects.create(
        client=client,
        kind=payload.code,
        category=category,
        polarity=polarity,
        weight=Decimal(weight),
        title=label,
        detail=note,
        occurred_at=timezone.make_aware(datetime.combine(occurred_on, time(12, 0))),
    )
    from ledger.api import _refresh_score

    result = _refresh_score(client)
    # Refresh all profiles, because matching the new evidence can change alerts
    # on more than one client. This does not change other clients' health scores.
    analyses = refresh_intelligence()
    return {
        "id": client.id,
        "score": result.score,
        "analysis": analyses[client.id]["metrics"],
        "alerts": [
            _alert_dict(alert)
            for alert in _alerts_for_client(client)
            if alert.status == ClientPatternAlert.Status.OPEN
        ],
    }


@router.post("/alerts/{alert_id}/review")
@transaction.atomic
def review_alert(request, alert_id: int, payload: AlertReviewIn):
    if payload.status not in (
        ClientPatternAlert.Status.REVIEWED,
        ClientPatternAlert.Status.DISMISSED,
    ):
        raise HttpError(422, "Choose reviewed or dismissed.")
    if len(payload.note) > 500:
        raise HttpError(422, "Review note is too long.")
    try:
        alert = ClientPatternAlert.objects.select_related("client").get(pk=alert_id)
    except ClientPatternAlert.DoesNotExist as exc:
        raise HttpError(404, "Pattern alert not found.") from exc
    alert.status = payload.status
    alert.review_note = payload.note.strip()
    alert.save(update_fields=["status", "review_note", "updated_at"])
    Event.objects.create(
        client=alert.client,
        kind="pattern_reviewed",
        category=Event.Category.RELATIONSHIP,
        polarity=0,
        title="Pattern alert reviewed",
        detail=f"Alert {alert.id} marked {alert.status}.",
        occurred_at=timezone.now(),
    )
    return {"id": alert.id, "status": alert.status}


@router.post("/advice")
def request_client_advice(request, payload: AdviceIn):
    client = _get_client(payload.client_id)
    if payload.provider not in {"local", "gemini", "grok"}:
        raise HttpError(422, "Unsupported advice provider.")
    # The system's own rules never need an API key or permission to call outside.
    analyses = read_intelligence()
    if payload.provider == "local":
        return local_recommendations(client.id, analyses)

    if not payload.share_anonymized:
        raise HttpError(422, "Explicit approval is required to share anonymized indicators.")
    if (
        ClientAdvisoryReport.objects.filter(
            provider__in=["gemini", "grok"],
            created_at__gte=timezone.now() - timedelta(minutes=1),
        ).count()
        >= 3
    ):
        raise HttpError(429, "Too many model requests. Try again later.")
    alerts = [
        a for a in _alerts_for_client(client) if a.status != ClientPatternAlert.Status.RESOLVED
    ]
    evidence = evidence_for_provider(analyses, client.id, alerts)
    try:
        model_name, advice = request_advice(payload.provider, evidence)
    except AdviceUnavailable as exc:
        raise HttpError(503, str(exc)) from exc

    signature = sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
    ClientAdvisoryReport.objects.create(
        client=client,
        provider=payload.provider,
        model_name=model_name,
        evidence_signature=signature,
        advice=advice,
    )
    return {
        "provider": payload.provider,
        "model": model_name,
        "advice": advice,
        "disclaimer": (
            "An external model produced this second opinion; it may be inaccurate. "
            "The local score, client status, finances and alerts were not changed."
        ),
    }
