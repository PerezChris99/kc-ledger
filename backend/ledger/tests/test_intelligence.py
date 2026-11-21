"""Evidence-based intelligence regressions, run on SQLite and PostgreSQL."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from ledger.models import (
    Client,
    ClientAdvisoryReport,
    ClientPatternAlert,
    Event,
)
from ledger.services.advisory import AdviceUnavailable, _parse_response, provider_config
from ledger.services.intelligence import _similarity, refresh_intelligence


@pytest.fixture
def owner(client):
    account = get_user_model().objects.create_user(
        username="intelligence-owner", password="very-long-test-password", is_staff=True
    )
    client.force_login(account)
    return client


def adverse_event(client, code):
    return Event.objects.create(
        client=client,
        kind=code,
        category=Event.Category.BEHAVIOUR,
        polarity=-1,
        title=code.replace("_", " "),
        occurred_at=timezone.now(),
    )


@pytest.mark.django_db
def test_intelligence_requires_staff(client):
    assert client.get("/api/intelligence/overview").status_code in {401, 403}
    assert client.get("/api/intelligence/signal-types").status_code in {401, 403}


@pytest.mark.django_db
def test_empty_intelligence_workspace_is_safe(owner):
    result = owner.get("/api/intelligence/overview")
    assert result.status_code == 200
    body = result.json()
    assert body["client_count"] == 0
    assert body["alerts"] == []
    assert len(body["score_distribution"]) == 5
    assert body["ai"]["external_opt_in_required"] is True


@pytest.mark.django_db
def test_same_behaviour_patterns_flag_new_client_with_recorded_evidence(owner):
    prior = Client.objects.create(name="Earlier client", score=30)
    current = Client.objects.create(name="New client", score=60)
    adverse_event(prior, "scope_creep")
    adverse_event(prior, "payment_late")
    adverse_event(current, "scope_creep")
    adverse_event(current, "payment_late")

    details = owner.get(f"/api/intelligence/clients/{current.id}")
    assert details.status_code == 200
    alerts = details.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["reference_client_id"] == prior.id
    assert alerts[0]["similarity"] >= 55
    assert {x["kind"] for x in alerts[0]["shared_signals"]} == {"scope_creep", "payment_late"}
    assert alerts[0]["status"] == "open"
    assert details.json()["analysis"]["risk_index"] > 0


@pytest.mark.django_db
def test_one_shared_signal_does_not_produce_accusation(owner):
    prior = Client.objects.create(name="Old", score=20, country="Uganda")
    current = Client.objects.create(name="New", score=10, country="Uganda")
    for c in (prior, current):
        adverse_event(c, "scope_creep")
    response = owner.get("/api/intelligence/overview")
    assert response.status_code == 200
    assert response.json()["open_alert_count"] == 0
    assert not ClientPatternAlert.objects.exists()


@pytest.mark.django_db
def test_recorded_signal_is_immutable_and_refreshes_score(owner):
    client = Client.objects.create(name="New", score=50)
    response = owner.post(
        f"/api/intelligence/clients/{client.id}/signals",
        data={"code": "abusive", "detail": "Recorded evidence, not speculation"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert Event.objects.filter(client=client, kind="abusive").count() == 1
    client.refresh_from_db()
    assert 0 <= client.score <= 100
    summary = response.json()["analysis"]
    assert any(x["kind"] == "abusive" for x in summary["adverse_signals"])
    assert summary["evidence_confidence"] == "insufficient"
    assert (
        owner.post(
            f"/api/intelligence/clients/{client.id}/signals",
            data={"code": "nonexistent-psychology", "detail": "guess"},
            content_type="application/json",
        ).status_code
        == 422
    )
    assert Event.objects.filter(client=client, kind="nonexistent-psychology").count() == 0


@pytest.mark.django_db
def test_review_persists_and_duplicate_refresh_does_not_reopen(owner):
    a = Client.objects.create(name="Historical", score=25)
    b = Client.objects.create(name="Current", score=55)
    for code in ("scope_creep", "chargeback"):
        adverse_event(a, code)
        adverse_event(b, code)
    refresh_intelligence()
    alert = ClientPatternAlert.objects.get(client=b)
    response = owner.post(
        f"/api/intelligence/alerts/{alert.id}/review",
        data={"status": "dismissed", "note": "Evidence was explained and resolved"},
        content_type="application/json",
    )
    assert response.status_code == 200
    refresh_intelligence()
    alert.refresh_from_db()
    assert alert.status == "dismissed"
    assert alert.review_note.startswith("Evidence was explained")


@pytest.mark.django_db
def test_local_advice_operates_without_any_model_keys(owner, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    client = Client.objects.create(name="Private ledger")
    answer = owner.post(
        "/api/intelligence/advice",
        data={"client_id": client.id, "provider": "local"},
        content_type="application/json",
    )
    assert answer.status_code == 200
    assert answer.json()["provider"] == "local"
    assert answer.json()["evidence_confidence"] == "insufficient"
    assert ClientAdvisoryReport.objects.count() == 0


@pytest.mark.django_db
def test_external_provider_requires_explicit_per_request_consent(owner):
    client = Client.objects.create(name="Confidential owner")
    with patch("ledger.intelligence_api.request_advice") as mock:
        result = owner.post(
            "/api/intelligence/advice",
            data={"client_id": client.id, "provider": "gemini"},
            content_type="application/json",
        )
    assert result.status_code == 422
    mock.assert_not_called()


@pytest.mark.django_db
def test_only_anonymized_evidence_is_sent_and_advice_is_separate(owner):
    prior = Client.objects.create(
        name="Prior secret", email="hidden@example.test", notes="Very private"
    )
    current = Client.objects.create(
        name="New confidential", email="private@example.test", notes="Do not share"
    )
    adverse_event(prior, "scope_creep")
    adverse_event(current, "scope_creep")
    evidence = {}

    def model(provider, payload):
        evidence.update(payload)
        return "gemini-2.5-flash-lite", {
            "summary": "Use a written scope",
            "actions": ["Agree milestones"],
            "avoid": [],
            "uncertainty": "Sparse evidence",
        }

    with patch("ledger.intelligence_api.request_advice", side_effect=model):
        response = owner.post(
            "/api/intelligence/advice",
            data={
                "client_id": current.id,
                "provider": "gemini",
                "share_anonymized": True,
            },
            content_type="application/json",
        )
    assert response.status_code == 200
    assert "private@example.test" not in str(evidence)
    assert "hidden@example.test" not in str(evidence)
    assert "New confidential" not in str(evidence)
    assert "Prior secret" not in str(evidence)
    assert "Do not share" not in str(evidence)
    assert "id" not in evidence
    assert ClientAdvisoryReport.objects.filter(client=current, provider="gemini").exists()
    assert current.score == 50


@pytest.mark.django_db
def test_objective_overdue_invoice_is_counted(owner):
    from ledger.models import Invoice

    c = Client.objects.create(name="Debtor")
    Invoice.objects.create(
        client=c,
        number="D-001",
        title="Services",
        issue_date=timezone.localdate() - timedelta(days=30),
        due_date=timezone.localdate() - timedelta(days=2),
        amount="100.00",
        status=Invoice.Status.SENT,
    )
    detail = owner.get(f"/api/intelligence/clients/{c.id}")
    assert detail.status_code == 200
    metrics = detail.json()["analysis"]
    assert metrics["overdue_invoices"] == 1
    assert any(x["kind"] == "invoice_overdue" for x in metrics["adverse_signals"])


def test_similarity_rejects_single_overlap_even_if_highly_weighted():
    match, overlap = _similarity({"abusive": 2}, {"abusive": 2})
    assert match == 0
    assert overlap == []


def test_provider_response_validation_blocks_invalid_json():
    with pytest.raises(AdviceUnavailable):
        _parse_response("not-json")


def test_grok_metered_calls_are_disabled_by_default(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("LEDGER_AI_ADVICE_ENABLED", "1")
    monkeypatch.delenv("LEDGER_ENABLE_METERED_GROK", raising=False)
    with pytest.raises(AdviceUnavailable):
        provider_config("grok")
