"""Owner-governed business intelligence and strategy experiment ledger API."""

import json
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256

from django.db import transaction
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from ledger.models import (
    BusinessAdvisoryReport,
    BusinessObjective,
    BusinessStrategyDecision,
    Client,
    ClientAdvisoryReport,
    Event,
)
from ledger.services.advisory import (
    AdviceUnavailable,
    public_availability,
    request_advice,
)
from ledger.services.business_intelligence import (
    METRIC_MINIMIZE,
    amount,
    build_business_snapshot,
    decision_review,
    objective_progress,
    pitch_playbook,
    prioritize_goals_and_decisions,
    recommend_strategy_paths,
    simulate,
)

router = Router(tags=["business-intelligence"])
METRICS = {item.value for item in BusinessObjective.Metric}
KINDS = {item.value for item in BusinessStrategyDecision.Kind}


class ObjectiveIn(Schema):
    name: str
    metric: str
    target: Decimal
    due_date: date
    description: str = ""


class ObjectiveUpdate(Schema):
    status: str


class StrategyIn(Schema):
    title: str
    kind: str
    metric: str
    review_on: date
    rationale: str = ""
    expected_effect: str = ""
    objective_id: int | None = None
    client_id: int | None = None
    started_on: date | None = None


class StrategyReview(Schema):
    status: str
    outcome_note: str = ""


class BusinessAdviceIn(Schema):
    provider: str = "local"
    share_anonymized: bool = False


def _safe_text(value, limit, name, required=False):
    cleaned = value.strip()
    if len(cleaned) > limit or (required and not cleaned):
        raise HttpError(
            422, f"{name} must have 1–{limit} characters." if required else f"{name} is too long."
        )
    return cleaned


def _check_metric(metric):
    if metric not in METRICS:
        raise HttpError(422, "Unsupported measurable business outcome.")


def _validate_target(value):
    if not value.is_finite() or abs(value) > Decimal(999999999999999):
        raise HttpError(422, "Target is not a finite supported amount.")
    if value.as_tuple().exponent < -2:
        raise HttpError(422, "Targets support up to two decimal places.")
    return value


def _validate_dates(start, end):
    if start > timezone.localdate() or end < start:
        raise HttpError(422, "Strategy review must not predate the start date.")
    if end > timezone.localdate() + timedelta(days=730):
        raise HttpError(422, "Review dates must be within two years.")


def _record_audit(kind, title, detail, client=None):
    Event.objects.create(
        client=client,
        kind=kind,
        category=Event.Category.RELATIONSHIP,
        polarity=0,
        title=title,
        detail=detail[:500],
        occurred_at=timezone.now(),
    )


def _portfolio(include_decisions=True):
    snapshot = build_business_snapshot()
    objectives = list(BusinessObjective.objects.order_by("due_date", "id")[:100])
    decisions = (
        list(
            BusinessStrategyDecision.objects.select_related("client", "objective").order_by(
                "-created_at"
            )[:150]
        )
        if include_decisions
        else []
    )
    result = {key: value for key, value in snapshot.items() if key != "metric_values"}
    result["objectives"] = [objective_progress(row, snapshot) for row in objectives]
    result["decisions"] = [decision_review(row, snapshot) for row in decisions]
    result["recommendations"] = prioritize_goals_and_decisions(snapshot, objectives, decisions)
    result["strategy_paths"] = recommend_strategy_paths(snapshot, objectives, decisions)
    result["provider_status"] = public_availability()
    result["scope"] = "business-operations"
    result["methodology"] = (
        "Rules analyze current recorded ledger data and explicitly declared objectives. "
        "Previous strategies are compared by before/after metric, without causal inference. "
        "Projections are constrained historical scenarios. External advice is optional."
    )
    return result, snapshot


@router.get("/overview")
def business_overview(request):
    data, _ = _portfolio()
    data["scope"] = "business-operations"
    return data


@router.get("/pitch/{client_id}")
def business_pitch(request, client_id: int):
    try:
        client = Client.objects.get(pk=client_id)
    except Client.DoesNotExist as exc:
        raise HttpError(404, "Client not found.") from exc
    return pitch_playbook(client, build_business_snapshot())


@router.get("/scenario")
def business_scenario(
    request,
    pricing_pct: float = 0,
    collection_pct: float = 0,
    expenses_pct: float = 0,
):
    if (
        not -40 <= pricing_pct <= 100
        or not -40 <= collection_pct <= 100
        or not -80 <= expenses_pct <= 100
    ):
        raise HttpError(422, "Scenario levers exceed permitted ranges.")
    if any(not Decimal(str(n)).is_finite() for n in (pricing_pct, collection_pct, expenses_pct)):
        raise HttpError(422, "Scenario inputs must be finite numbers.")
    return simulate(
        build_business_snapshot(),
        pricing_pct=pricing_pct,
        collection_pct=collection_pct,
        expenses_pct=expenses_pct,
    )


@router.post("/objectives")
@transaction.atomic
def create_objective(request, payload: ObjectiveIn):
    _check_metric(payload.metric)
    name = _safe_text(payload.name, 140, "Objective name", required=True)
    description = _safe_text(payload.description, 800, "Objective description")
    target = _validate_target(payload.target)
    if (
        payload.metric
        in METRIC_MINIMIZE.union(
            {BusinessObjective.Metric.ACTIVE_CLIENTS, BusinessObjective.Metric.MONTHLY_RECEIPTS}
        )
        and target < 0
    ):
        raise HttpError(422, "This objective cannot use a negative target.")
    if payload.metric == BusinessObjective.Metric.ACTIVE_CLIENTS and target % 1:
        raise HttpError(422, "Client count targets must be whole numbers.")
    if payload.due_date < timezone.localdate():
        raise HttpError(422, "Objective deadlines must be today or later.")
    if payload.due_date > timezone.localdate() + timedelta(days=1825):
        raise HttpError(422, "Objective deadlines must be within five years.")
    item = BusinessObjective.objects.create(
        name=name,
        metric=payload.metric,
        target=target,
        due_date=payload.due_date,
        description=description,
    )
    _record_audit(
        "business_objective_created",
        "Business objective recorded",
        f"Goal {item.id}: {item.metric} target {amount(item.target)}.",
    )
    return {"id": item.id, "status": item.status}


@router.patch("/objectives/{objective_id}")
@transaction.atomic
def update_objective(request, objective_id: int, payload: ObjectiveUpdate):
    if payload.status not in BusinessObjective.Status.values:
        raise HttpError(422, "Unsupported objective status.")
    try:
        row = BusinessObjective.objects.get(pk=objective_id)
    except BusinessObjective.DoesNotExist as exc:
        raise HttpError(404, "Objective not found.") from exc
    row.status = payload.status
    row.save(update_fields=["status", "updated_at"])
    _record_audit(
        "business_objective_status",
        "Business objective status updated",
        f"Goal {row.id} changed to {row.status}.",
    )
    return {"id": row.id, "status": row.status}


@router.post("/decisions")
@transaction.atomic
def create_strategy_decision(request, payload: StrategyIn):
    _check_metric(payload.metric)
    if payload.kind not in KINDS:
        raise HttpError(422, "Unsupported strategy category.")
    title = _safe_text(payload.title, 160, "Strategy title", required=True)
    rationale = _safe_text(payload.rationale, 900, "Strategy rationale")
    expected = _safe_text(payload.expected_effect, 280, "Expected effect")
    start = payload.started_on or timezone.localdate()
    _validate_dates(start, payload.review_on)
    if start < timezone.localdate() - timedelta(days=3650):
        raise HttpError(422, "Historical strategy dates can go back up to ten years.")
    if payload.objective_id:
        try:
            objective = BusinessObjective.objects.get(pk=payload.objective_id)
        except BusinessObjective.DoesNotExist as exc:
            raise HttpError(422, "Linked business objective does not exist.") from exc
        if objective.metric != payload.metric:
            raise HttpError(422, "Strategy metric must match the linked objective.")
    else:
        objective = None
    if payload.client_id:
        try:
            client = Client.objects.get(pk=payload.client_id)
        except Client.DoesNotExist as exc:
            raise HttpError(422, "Linked client does not exist.") from exc
    else:
        client = None
    snapshot = build_business_snapshot()
    current = snapshot["metric_values"].get(payload.metric)
    no_fx_gap = not snapshot["data_quality"]["missing_fx"] or (
        payload.metric == BusinessObjective.Metric.ACTIVE_CLIENTS
    )
    # A historical baseline cannot be reconstructed honestly from a live snapshot.
    baseline = current if start == timezone.localdate() and no_fx_gap else None
    row = BusinessStrategyDecision.objects.create(
        title=title,
        kind=payload.kind,
        rationale=rationale,
        expected_effect=expected,
        metric=payload.metric,
        objective=objective,
        client=client,
        baseline=baseline,
        started_on=start,
        review_on=payload.review_on,
        status=BusinessStrategyDecision.Status.ACTIVE
        if start <= timezone.localdate()
        else BusinessStrategyDecision.Status.PLANNED,
    )
    _record_audit(
        "business_strategy_created",
        "Business strategy recorded",
        f"Strategy {row.id}: {row.kind} / {row.metric}; review {row.review_on}.",
        client=client,
    )
    return {
        "id": row.id,
        "status": row.status,
        "baseline": amount(baseline) if baseline is not None else None,
        "note": "Historical baselines are left unknown rather than fabricated."
        if baseline is None
        else "Baseline captured from the current recorded ledger.",
    }


@router.patch("/decisions/{decision_id}")
@transaction.atomic
def review_strategy_decision(request, decision_id: int, payload: StrategyReview):
    if payload.status not in BusinessStrategyDecision.Status.values:
        raise HttpError(422, "Unsupported decision status.")
    outcome = _safe_text(payload.outcome_note, 1200, "Outcome note")
    try:
        row = BusinessStrategyDecision.objects.get(pk=decision_id)
    except BusinessStrategyDecision.DoesNotExist as exc:
        raise HttpError(404, "Strategy decision not found.") from exc
    row.status = payload.status
    row.outcome_note = outcome
    row.save(update_fields=["status", "outcome_note", "updated_at"])
    _record_audit(
        "business_strategy_reviewed",
        "Business strategy reviewed",
        f"Strategy {row.id} moved to {row.status}.",
        client=row.client,
    )
    return {"id": row.id, "status": row.status}


def _anonymized_business_context(snapshot, objectives, decisions):
    """No free text, names, contacts, monetary amounts, or client identities."""
    metrics = snapshot["metrics"]
    collected = Decimal(metrics["collected"])
    expenses = Decimal(metrics["expenses"])
    outstanding = Decimal(metrics["outstanding"])
    return {
        "analysis_scope": "business",
        "context_version": 1,
        "receipt_count": metrics["receipt_count"],
        "expense_count": metrics["expense_count"],
        "active_client_count": metrics["active_clients"],
        "expenses_to_receipts_pct": round(float(expenses / collected * 100), 1)
        if collected
        else None,
        "overdue_to_unpaid_pct": round(float(Decimal(metrics["overdue"]) / outstanding * 100), 1)
        if outstanding
        else None,
        "top_client_receipts_pct": metrics["top_client_share_pct"],
        "has_missing_fx": bool(snapshot["data_quality"]["missing_fx"]),
        "expense_capture_verified": False,
        "forecast_available": snapshot["forecast"]["available"],
        "anomaly_codes": [entry["id"] for entry in snapshot["anomalies"][:8]],
        "rule_codes": [entry["id"] for entry in snapshot["recommendations"][:15]],
        "goals": [
            {
                "metric": row["metric"],
                "direction": row["direction"],
                "is_met": row["favorable"],
                "days_remaining": row["days_remaining"],
            }
            for row in objectives
            if row["status"] == BusinessObjective.Status.ACTIVE
        ][:15],
        "strategy_outcomes": [
            {
                "kind": row["kind"],
                "metric": row["metric"],
                "review_due": row["review_due"],
                "direction_favorable": row["direction_favorable"],
            }
            for row in decisions[:20]
        ],
        "notes": [
            "Financial indicators are recorded cash movements, not accounting profit.",
            "Rule and metric context has incomplete expense-coverage verification.",
        ],
    }


@router.post("/advice")
def business_advice(request, payload: BusinessAdviceIn):
    if payload.provider not in {"local", "gemini", "grok"}:
        raise HttpError(422, "Unsupported strategy advisory provider.")
    overview, snapshot = _portfolio()
    if payload.provider == "local":
        return {
            "provider": "local",
            "model": "business-rules-v1",
            "summary": (
                "Insufficient financial history for reliable trend analysis."
                if snapshot["metrics"]["receipt_count"] + snapshot["metrics"]["expense_count"] < 3
                else "Review these evidence-backed business priorities."
            ),
            "actions": [row["action"] for row in overview["recommendations"][:8]],
            "avoid": [row["avoid"] for row in overview["recommendations"][:5]],
            "evidence": overview["recommendations"][:8],
            "data_quality": snapshot["data_quality"],
        }
    if not payload.share_anonymized:
        raise HttpError(422, "Explicit consent required for this single provider request.")
    if (
        BusinessAdvisoryReport.objects.filter(
            created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        + ClientAdvisoryReport.objects.filter(
            provider__in=["gemini", "grok"], created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        >= 3
    ):
        raise HttpError(429, "Model advice rate limit reached.")
    evidence = _anonymized_business_context(snapshot, overview["objectives"], overview["decisions"])
    try:
        model, result = request_advice(payload.provider, evidence)
    except AdviceUnavailable as exc:
        raise HttpError(503, str(exc)) from exc
    signature = sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
    BusinessAdvisoryReport.objects.create(
        provider=payload.provider, model_name=model, evidence_signature=signature, advice=result
    )
    return {
        "provider": payload.provider,
        "model": model,
        "advice": result,
        "disclaimer": (
            "External second opinion, not business forecasts or verified financial advice. "
            "No ledger, goal, client classification or strategy record was modified."
        ),
    }
