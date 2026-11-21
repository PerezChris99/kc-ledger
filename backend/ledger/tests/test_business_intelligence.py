"""Business-command core: cash integrity, evidence, goals and strategy safety."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from ledger.models import (
    BusinessAdvisoryReport,
    BusinessObjective,
    BusinessStrategyDecision,
    Client,
    Expense,
    Invoice,
    Payment,
)
from ledger.services.business_intelligence import (
    build_business_snapshot,
    simulate,
)


@pytest.fixture
def owner(client):
    user = get_user_model().objects.create_user(
        username="business-test-owner",
        password="really-long-private-test-password",
        is_staff=True,
    )
    client.force_login(user)
    return client


@pytest.fixture
def paid_client():
    return Client.objects.create(name="Recorded Services Buyer")


def invoice(client, amount, due, status=Invoice.Status.SENT, number="INV-BUS-1"):
    return Invoice.objects.create(
        client=client,
        number=number,
        title="Test delivery",
        issue_date=due - timedelta(days=10),
        due_date=due,
        amount=Decimal(str(amount)),
        currency="USD",
        status=status,
    )


@pytest.mark.django_db
def test_business_endpoints_require_staff(client):
    for url in (
        "/api/intelligence/business/overview",
        "/api/intelligence/business/scenario",
        "/api/intelligence/business/pitch/1",
    ):
        assert client.get(url).status_code in {401, 403}
    assert client.post(
        "/api/intelligence/business/objectives",
        data={},
        content_type="application/json",
    ).status_code in {401, 403}


@pytest.mark.django_db
def test_cash_metrics_and_outstanding_are_not_misrepresented_as_profit(paid_client):
    inv = invoice(paid_client, 200, timezone.localdate() - timedelta(days=12))
    Payment.objects.create(
        invoice=inv,
        client=paid_client,
        amount=Decimal(100),
        paid_on=timezone.localdate(),
    )
    Expense.objects.create(
        client=paid_client,
        category="Software",
        amount=Decimal(140),
        currency="USD",
        spent_on=timezone.localdate(),
    )
    result = build_business_snapshot(base="USD")
    assert result["metrics"]["collected"] == "100.00"
    assert result["metrics"]["expenses"] == "140.00"
    assert result["metrics"]["recorded_net_cash"] == "-40.00"
    assert result["metrics"]["outstanding"] == "100.00"
    assert result["metrics"]["overdue"] == "100.00"
    assert result["data_quality"]["expense_capture_verified"] is False
    assert "not audited accounting profit" in result["data_quality"]["classification"]
    assert result["client_contribution"][0]["direct_cash_contribution"] == "-40.00"
    assert {"negative_cash", "overdue_exposure"} <= {x["id"] for x in result["recommendations"]}


@pytest.mark.django_db
def test_unassigned_expenses_are_never_omitted_from_total(paid_client):
    inv = invoice(paid_client, 90, timezone.localdate() + timedelta(days=15))
    Payment.objects.create(
        invoice=inv,
        client=paid_client,
        amount=Decimal(90),
        paid_on=timezone.localdate(),
    )
    Expense.objects.create(
        category="Hosting",
        amount=Decimal(35),
        currency="USD",
        spent_on=timezone.localdate(),
    )
    result = build_business_snapshot(base="USD")
    assert result["metrics"]["expenses"] == "35.00"
    assert result["metrics"]["unassigned_expenses"] == "35.00"
    assert result["metrics"]["recorded_net_cash"] == "55.00"
    assert result["client_contribution"][0]["direct_cash_contribution"] == "90.00"
    assert result["data_quality"]["notes"]


@pytest.mark.django_db
def test_unconverted_currency_is_not_silently_added_as_zero(paid_client):
    Expense.objects.create(
        category="Foreign costs",
        currency="EUR",
        amount=Decimal(99),
        spent_on=timezone.localdate(),
    )
    result = build_business_snapshot(base="USD")
    assert result["metrics"]["expenses"] == "0.00"
    assert result["data_quality"]["missing_fx"] == ["EUR"]
    assert any(row["id"] == "fx_gaps" for row in result["recommendations"])


@pytest.mark.django_db
def test_insufficient_forecast_has_no_fabricated_estimate():
    result = build_business_snapshot(base="USD")
    assert result["forecast"]["available"] is False
    assert simulate(result, pricing_pct=12)["available"] is False
    assert any(row["id"] == "unmeasured_cash" for row in result["recommendations"])


@pytest.mark.django_db
def test_historical_anomaly_and_sensitivity_are_explainable(paid_client):
    first = timezone.localdate().replace(day=1)
    for n in (4, 3, 2, 1):
        y = first.year
        m = first.month - n
        while m <= 0:
            y -= 1
            m += 12
        day = date(y, m, 15)
        value = "500" if n == 1 else "100"
        inv = invoice(paid_client, value, day, status=Invoice.Status.PAID, number=f"ANOMALY-{n}")
        Payment.objects.create(
            client=paid_client,
            invoice=inv,
            amount=Decimal(value),
            paid_on=day,
        )
    snap = build_business_snapshot(base="USD")
    assert snap["forecast"]["available"] is True
    assert snap["forecast"]["confidence"] == "low"
    assert any(r["id"] == "receipts_deviation" for r in snap["anomalies"])
    scenario = simulate(snap, pricing_pct=10, collection_pct=0, expenses_pct=0)
    assert scenario["available"]
    assert Decimal(scenario["scenario_cash"]) > Decimal(scenario["baseline_cash"])
    assert "Sensitivity" in scenario["warning"]


@pytest.mark.django_db
def test_business_overview_returns_machine_readable_charts_and_quality(owner):
    r = owner.get("/api/intelligence/business/overview")
    assert r.status_code == 200
    data = r.json()
    assert data["currency"] == "USD"
    assert len(data["monthly"]) == 13
    assert len(data["aging"]) == 4
    assert data["objectives"] == []
    assert data["decisions"] == []
    assert data["scope"] == "business-operations"
    assert data["provider_status"]["external_opt_in_required"] is True


@pytest.mark.django_db
def test_objective_creation_reading_and_pause(owner):
    target = {
        "name": "Keep at least five active clients",
        "metric": "active_clients",
        "target": "5",
        "due_date": (timezone.localdate() + timedelta(days=90)).isoformat(),
    }
    resp = owner.post(
        "/api/intelligence/business/objectives",
        data=target,
        content_type="application/json",
    )
    assert resp.status_code == 200
    row = BusinessObjective.objects.get(pk=resp.json()["id"])
    overview = owner.get("/api/intelligence/business/overview").json()
    goal = overview["objectives"][0]
    assert goal["target"] == "5.00"
    assert goal["current"] == "0.00"
    assert goal["favorable"] is False
    paused = owner.patch(
        f"/api/intelligence/business/objectives/{row.id}",
        data={"status": "paused"},
        content_type="application/json",
    )
    assert paused.status_code == 200
    row.refresh_from_db()
    assert row.status == "paused"


@pytest.mark.django_db
def test_goal_rejects_nonfinite_and_bad_metrics(owner):
    payload = {
        "name": "Invalid",
        "metric": "personality_prediction",
        "target": "1",
        "due_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
    }
    resp = owner.post(
        "/api/intelligence/business/objectives",
        data=payload,
        content_type="application/json",
    )
    assert resp.status_code == 422
    payload["metric"] = "active_clients"
    payload["target"] = "2.5"
    resp = owner.post(
        "/api/intelligence/business/objectives",
        data=payload,
        content_type="application/json",
    )
    assert resp.status_code == 422


@pytest.mark.django_db
def test_strategy_baseline_and_review_do_not_change_finances(owner, paid_client):
    payload = {
        "title": "Use deposits for new projects",
        "kind": "collections",
        "metric": "monthly_receipts",
        "rationale": "Payments arrive too late",
        "expected_effect": "Shorter collection delays",
        "review_on": (timezone.localdate() + timedelta(days=30)).isoformat(),
        "client_id": paid_client.id,
    }
    res = owner.post(
        "/api/intelligence/business/decisions",
        data=payload,
        content_type="application/json",
    )
    assert res.status_code == 200
    decision_id = res.json()["id"]
    row = BusinessStrategyDecision.objects.get(id=decision_id)
    assert row.baseline == Decimal(0)
    assert row.client_id == paid_client.id
    # A new decision cannot claim success before a dated owner review.
    assert (
        owner.get("/api/intelligence/business/overview").json()["decisions"][0][
            "direction_favorable"
        ]
        is None
    )
    review = owner.patch(
        f"/api/intelligence/business/decisions/{decision_id}",
        data={"status": "reviewed", "outcome_note": "Await 3 more client cycles"},
        content_type="application/json",
    )
    assert review.status_code == 200
    assert review.json()["review_quality"] == "early_review"
    assert review.json()["review_favorable"] is None
    assert BusinessStrategyDecision.objects.get(id=decision_id).status == "reviewed"
    assert Invoice.objects.count() == 0


@pytest.mark.django_db
def test_historical_strategy_never_invents_baseline(owner):
    started = timezone.localdate() - timedelta(days=80)
    res = owner.post(
        "/api/intelligence/business/decisions",
        data={
            "title": "Earlier price experiment",
            "kind": "pricing",
            "metric": "monthly_cash_result",
            "review_on": (started + timedelta(days=50)).isoformat(),
            "started_on": started.isoformat(),
        },
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json()["baseline"] is None
    assert "rather than fabricated" in res.json()["note"]


@pytest.mark.django_db
def test_strategy_goal_metric_must_match(owner):
    goal = BusinessObjective.objects.create(
        name="Reduce overdue",
        metric="overdue_balance",
        target=Decimal(0),
        due_date=timezone.localdate() + timedelta(days=50),
    )
    r = owner.post(
        "/api/intelligence/business/decisions",
        data={
            "title": "Change pitch language",
            "kind": "outreach",
            "metric": "monthly_receipts",
            "objective_id": goal.id,
            "review_on": (timezone.localdate() + timedelta(days=40)).isoformat(),
        },
        content_type="application/json",
    )
    assert r.status_code == 422
    assert not BusinessStrategyDecision.objects.exists()


@pytest.mark.django_db
def test_scenario_input_is_bounded(owner):
    assert owner.get("/api/intelligence/business/scenario?pricing_pct=1000").status_code == 422


@pytest.mark.django_db
def test_pitch_uses_contract_and_invoice_facts_not_personality(owner, paid_client):
    invoice(paid_client, 100, timezone.localdate() - timedelta(days=10), number="PITCH-OVERDUE")
    reply = owner.get(f"/api/intelligence/business/pitch/{paid_client.id}")
    assert reply.status_code == 200
    result = reply.json()
    assert result["has_overdue"]
    assert any("payment plan" in x for x in result["approach"])
    assert "personality" in result["avoid"]


@pytest.mark.django_db
def test_local_business_advice_requires_no_external_model(owner):
    with patch("ledger.business_api.request_advice") as fake:
        response = owner.post(
            "/api/intelligence/business/advice",
            data={"provider": "local"},
            content_type="application/json",
        )
    assert response.status_code == 200
    assert response.json()["provider"] == "local"
    fake.assert_not_called()
    assert BusinessAdvisoryReport.objects.count() == 0


@pytest.mark.django_db
def test_external_business_advice_requires_opt_in(owner):
    with patch("ledger.business_api.request_advice") as fake:
        reply = owner.post(
            "/api/intelligence/business/advice",
            data={"provider": "gemini"},
            content_type="application/json",
        )
    assert reply.status_code == 422
    fake.assert_not_called()


@pytest.mark.django_db
def test_business_model_only_receives_anonymous_ratios_not_private_text(owner, paid_client):
    Expense.objects.create(
        category="Private expense label",
        note="Secret vendor details",
        currency="USD",
        amount=Decimal(20),
        spent_on=timezone.localdate(),
    )
    BusinessObjective.objects.create(
        name="Secret long term competitive plan",
        description="Do not share this plan",
        metric="monthly_cash_result",
        target=Decimal(300),
        due_date=timezone.localdate() + timedelta(days=30),
    )
    leaked = {}

    def model(provider, context):
        leaked.update(context)
        return "gemini-test-model", {
            "summary": "Review cash coverage",
            "actions": ["Investigate costs"],
            "avoid": ["Unverified claims"],
            "uncertainty": "Very little evidence",
        }

    with patch("ledger.business_api.request_advice", side_effect=model):
        response = owner.post(
            "/api/intelligence/business/advice",
            data={"provider": "gemini", "share_anonymized": True},
            content_type="application/json",
        )
    assert response.status_code == 200
    assert response.json()["provider"] == "gemini"
    assert BusinessAdvisoryReport.objects.count() == 1
    text = str(leaked)
    for private in (
        paid_client.name,
        "Secret long term competitive plan",
        "Secret vendor details",
        "Private expense label",
        "Do not share this plan",
    ):
        assert private not in text
    assert "client_contribution" not in text
    assert "analysis_scope" in leaked


@pytest.mark.django_db
def test_business_alerts_emit_once_and_are_visible_to_notification_polling(owner, paid_client):
    from ledger.jobs import emit_business_intelligence_alerts
    from ledger.models import Event

    invoice(paid_client, 500, timezone.localdate() - timedelta(days=14), number="PROACTIVE-OVERDUE")
    before = Event.objects.filter(kind="business_alert_overdue_exposure").count()
    assert emit_business_intelligence_alerts() >= 1
    assert emit_business_intelligence_alerts() == 0
    assert Event.objects.filter(kind="business_alert_overdue_exposure").count() == before + 1
    since = (timezone.now() - timedelta(minutes=5)).isoformat()
    from urllib.parse import quote

    response = owner.get("/api/notifications?since=" + quote(since, safe=""))
    assert response.status_code == 200
    assert any(row["kind"] == "business_alert_overdue_exposure" for row in response.json()["items"])


@pytest.mark.django_db
def test_scheduled_business_alerts_do_not_invent_risk_on_empty_ledger():
    from ledger.jobs import emit_business_intelligence_alerts
    from ledger.models import Event

    assert emit_business_intelligence_alerts() == 0
    assert not Event.objects.filter(kind__startswith="business_alert_").exists()


@pytest.mark.django_db
def test_strategy_priorities_align_to_goals_and_reject_causal_claims():
    from ledger.services.business_intelligence import recommend_strategy_paths

    snapshot = build_business_snapshot(base="USD")
    objective = BusinessObjective.objects.create(
        name="Grow clients",
        metric=BusinessObjective.Metric.ACTIVE_CLIENTS,
        target=Decimal(10),
        due_date=timezone.localdate() + timedelta(days=120),
    )
    options = recommend_strategy_paths(snapshot, [objective], [])
    diversify = next(row for row in options if row["id"] == "diversify")
    assert "active_clients" in diversify["related_goals"]
    assert diversify["rank_score"] > 0
    assert "do not prove" in diversify["limitations"]


@pytest.mark.django_db
def test_strategy_ranking_shows_reviewed_unfavorable_outcome_without_false_causality():
    from ledger.services.business_intelligence import recommend_strategy_paths

    snapshot = build_business_snapshot(base="USD")
    strategy = BusinessStrategyDecision.objects.create(
        title="Prior cost cutting",
        kind="costs",
        metric="monthly_cash_result",
        baseline=Decimal(100),
        started_on=timezone.localdate() - timedelta(days=30),
        review_on=timezone.localdate(),
        status=BusinessStrategyDecision.Status.REVIEWED,
        reviewed_at=timezone.now(),
        review_value=Decimal(0),
        review_change=Decimal(-100),
        review_favorable=False,
        review_quality="observed",
    )
    goal = BusinessObjective.objects.create(
        name="Increase cash",
        metric="monthly_cash_result",
        target=Decimal(1000),
        due_date=timezone.localdate() + timedelta(days=30),
    )
    recommendations = recommend_strategy_paths(snapshot, [goal], [strategy])
    cost = next(row for row in recommendations if row["id"] == "cost_review")
    assert cost["past_unfavorable_observations"] == 1
    assert "caused" in cost["limitations"]


@pytest.mark.django_db
def test_archived_clients_still_account_for_historical_cash_not_current_pitches(paid_client):
    invoiced = invoice(
        paid_client, 120, timezone.localdate() + timedelta(days=5), number="ARCHIVED-CASH-1"
    )
    Payment.objects.create(
        client=paid_client, invoice=invoiced, amount=Decimal("120.00"), paid_on=timezone.localdate()
    )
    paid_client.delete()
    report = build_business_snapshot(base="USD")
    assert report["metrics"]["collected"] == "120.00"
    assert report["metrics"]["active_clients"] == 0
    assert report["metrics"]["client_count"] == 0
    row = next(x for x in report["client_contribution"] if x["id"] == paid_client.id)
    assert row["is_archived"] is True
    assert row["receipts"] == "120.00"
    assert report["metrics"]["top_client_share_pct"] == 100.0


@pytest.mark.django_db
def test_cash_goals_and_decision_baselines_fail_closed_after_currency_change():
    from ledger.services.business_intelligence import decision_review, objective_progress

    goal = BusinessObjective.objects.create(
        name="Cash safety",
        metric="monthly_cash_result",
        currency="USD",
        target=Decimal(50),
        due_date=timezone.localdate() + timedelta(days=15),
    )
    decision = BusinessStrategyDecision.objects.create(
        title="Previous baseline",
        kind="pricing",
        metric="monthly_cash_result",
        currency="USD",
        baseline=Decimal(75),
        started_on=timezone.localdate(),
        review_on=timezone.localdate(),
    )
    changed = build_business_snapshot(base="UGX")
    g = objective_progress(goal, changed)
    d = decision_review(decision, changed)
    assert g["currency_mismatch"] is True
    assert g["current"] is None
    assert g["favorable"] is None
    assert d["currency_mismatch"] is True
    assert d["observed_change"] is None
    assert d["direction_favorable"] is None


@pytest.mark.django_db
def test_strategy_review_is_frozen_and_no_change_is_not_a_success(owner, paid_client):
    from ledger.services.business_intelligence import decision_review

    decision = BusinessStrategyDecision.objects.create(
        title="Trial milestone deposits",
        kind=BusinessStrategyDecision.Kind.COLLECTIONS,
        metric=BusinessObjective.Metric.MONTHLY_RECEIPTS,
        baseline=Decimal(0),
        currency="USD",
        started_on=timezone.localdate(),
        review_on=timezone.localdate(),
        status=BusinessStrategyDecision.Status.ACTIVE,
    )
    endpoint = f"/api/intelligence/business/decisions/{decision.id}"
    response = owner.patch(
        endpoint,
        data={"status": "reviewed", "outcome_note": "No recorded change yet"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["review_quality"] == "unchanged"
    assert response.json()["review_favorable"] is None
    decision.refresh_from_db()
    frozen = (decision.reviewed_at, decision.review_value, decision.review_change)
    assert frozen[1] == Decimal(0)
    assert frozen[2] == Decimal(0)
    assert decision.review_favorable is None
    # This new payment changes live totals, but may not rewrite the review.
    from ledger.services.business_intelligence import _shift_month

    paid_on = _shift_month(timezone.localdate(), -1) + timedelta(days=12)
    recent = invoice(
        paid_client,
        130,
        paid_on + timedelta(days=3),
        number="REVIEW-FROZEN-INVOICE",
    )
    Payment.objects.create(client=paid_client, invoice=recent, amount=Decimal(130), paid_on=paid_on)
    live = build_business_snapshot(base="USD")
    shown = decision_review(decision, live)
    assert shown["review_quality"] == "unchanged"
    assert shown["observed_change"] == "0.00"
    assert shown["direction_favorable"] is None
    assert shown["current"] != shown["review_value"]
    again = owner.patch(
        endpoint,
        data={"status": "reviewed", "outcome_note": "Rewrite history"},
        content_type="application/json",
    )
    assert again.status_code == 409
    decision.refresh_from_db()
    assert (decision.reviewed_at, decision.review_value, decision.review_change) == frozen


@pytest.mark.django_db
def test_review_of_unmeasurable_strategy_stores_data_quality_instead_of_win(owner):
    from ledger.services.business_intelligence import decision_review

    strategy = BusinessStrategyDecision.objects.create(
        title="Unknown baseline",
        kind=BusinessStrategyDecision.Kind.OTHER,
        metric=BusinessObjective.Metric.MONTHLY_RECEIPTS,
        baseline=None,
        review_on=timezone.localdate(),
        started_on=timezone.localdate() - timedelta(days=12),
        status=BusinessStrategyDecision.Status.ACTIVE,
    )
    response = owner.patch(
        f"/api/intelligence/business/decisions/{strategy.id}",
        data={"status": "reviewed", "outcome_note": "No prior trustworthy baseline"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["review_quality"] == "missing_baseline"
    assert response.json()["review_favorable"] is None
    strategy.refresh_from_db()
    assert decision_review(strategy, build_business_snapshot(base="USD"))["review_value"] is None


@pytest.mark.django_db
def test_future_dated_financial_entries_never_inflate_current_cash(paid_client):
    today = timezone.localdate()
    inv = invoice(
        paid_client,
        100,
        today + timedelta(days=12),
        number="FUTURE-VALID-INVOICE",
    )
    Payment.objects.create(
        client=paid_client, invoice=inv, amount=Decimal(100), paid_on=today + timedelta(days=14)
    )
    Expense.objects.create(
        category="Future plan",
        amount=Decimal(70),
        currency="USD",
        spent_on=today + timedelta(days=20),
    )
    snap = build_business_snapshot(base="USD")
    assert snap["metrics"]["collected"] == "0.00"
    assert snap["metrics"]["expenses"] == "0.00"
    assert snap["metrics"]["recorded_net_cash"] == "0.00"
    assert snap["data_quality"]["future_dated_excluded"]["payments"] == 1
    assert snap["data_quality"]["future_dated_excluded"]["expenses"] == 1
    assert any(r["id"] == "future_dated_records" for r in snap["recommendations"])


@pytest.mark.django_db
def test_forecast_refuses_partial_currency_conversion_even_with_history(paid_client):
    for months in (4, 3, 2):
        anchor = timezone.localdate().replace(day=1)
        from ledger.services.business_intelligence import _shift_month

        date_paid = _shift_month(anchor, -months) + timedelta(days=8)
        inv = invoice(paid_client, 100, date_paid, number=f"MISSING-FX-{months}")
        Payment.objects.create(
            invoice=inv, client=paid_client, amount=Decimal(100), paid_on=date_paid
        )
    Expense.objects.create(
        category="Unconverted expense",
        amount=Decimal(25),
        currency="EUR",
        spent_on=timezone.localdate(),
    )
    snap = build_business_snapshot(base="USD")
    assert snap["forecast"]["available"] is False
    assert "FX" in snap["forecast"]["reason"]
    assert snap["anomalies"] == []


@pytest.mark.django_db
def test_sales_pipeline_records_factual_outcomes_not_booked_revenue(owner):
    from ledger.models import BusinessOpportunity, Event

    create = owner.post(
        "/api/intelligence/business/opportunities",
        data={
            "name": "Scope-first proposal",
            "source": "referral",
            "proposed_amount": "340",
            "currency": "USD",
            "next_action": "Review the delivery brief",
        },
        content_type="application/json",
    )
    assert create.status_code == 200, create.content
    row_id = create.json()["id"]
    initial = owner.get("/api/intelligence/business/overview").json()
    assert initial["pipeline"]["total_open"] == 1
    assert initial["pipeline"]["observed_win_share_pct"] is None
    assert initial["metrics"]["collected"] == "0.00"
    move = owner.patch(
        f"/api/intelligence/business/opportunities/{row_id}",
        data={"stage": "won", "next_action": "Issue signed contract"},
        content_type="application/json",
    )
    assert move.status_code == 200
    assert BusinessOpportunity.objects.get(id=row_id).closed_on == timezone.localdate()
    final = owner.get("/api/intelligence/business/overview").json()
    assert final["pipeline"]["won"] == 1
    assert final["pipeline"]["closed_sample"] == 1
    assert final["pipeline"]["observed_win_share_pct"] is None
    assert final["metrics"]["collected"] == "0.00"
    assert Event.objects.filter(kind="opportunity_stage_changed").exists()
    # Fixing a falsely marked win is auditable and does not invent financial movements.
    correct = owner.patch(
        f"/api/intelligence/business/opportunities/{row_id}",
        data={"stage": "lost", "lost_reason": "Budget not approved"},
        content_type="application/json",
    )
    assert correct.status_code == 200
    assert owner.get("/api/intelligence/business/overview").json()["pipeline"]["lost"] == 1


@pytest.mark.django_db
def test_sales_pipeline_validates_currency_quote_and_source(owner):
    base = {"name": "Proposal", "source": "referral", "proposed_amount": "100", "currency": "USD"}
    for changes in (
        {"source": "personality_guess"},
        {"proposed_amount": "-5"},
        {"proposed_amount": "NaN"},
        {"currency": "BADCODE"},
        {"name": " "},
    ):
        payload = {**base, **changes}
        response = owner.post(
            "/api/intelligence/business/opportunities",
            data=payload,
            content_type="application/json",
        )
        assert response.status_code == 422, (payload, response.content)


@pytest.mark.django_db
def test_observed_sales_win_share_requires_five_closed_cases():
    from ledger.models import BusinessOpportunity
    from ledger.services.sales_pipeline import pipeline_overview

    for i in range(4):
        BusinessOpportunity.objects.create(
            name=f"Sales case {i}",
            stage=(BusinessOpportunity.Stage.WON if i < 3 else BusinessOpportunity.Stage.LOST),
            source="outbound",
            currency="USD",
            proposed_amount=Decimal(200),
            opened_on=timezone.localdate() - timedelta(days=25),
            closed_on=timezone.localdate() - timedelta(days=2),
        )
    assert pipeline_overview()["observed_win_share_pct"] is None
    BusinessOpportunity.objects.create(
        name="Fifth case",
        stage=BusinessOpportunity.Stage.LOST,
        source="outbound",
        currency="USD",
        proposed_amount=Decimal(200),
        opened_on=timezone.localdate(),
        closed_on=timezone.localdate(),
    )
    result = pipeline_overview()
    assert result["closed_sample"] == 5
    assert result["observed_win_share_pct"] == 60.0
    assert "not a sales forecast" in result["limitations"]
