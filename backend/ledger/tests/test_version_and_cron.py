"""Build identity and serverless cron guard regressions."""

from unittest.mock import patch

import pytest
from config.version import build_info


def test_build_identity_uses_canonical_version():
    info = build_info()
    assert set(info) == {"version", "git_sha", "build_time", "channel", "min_supported_version"}
    assert info["version"] == "0.1.0"


@pytest.mark.django_db
def test_version_endpoint_has_no_sensitive_data(client):
    response = client.get("/api/version")
    assert response.status_code == 200
    assert response.json()["version"] == build_info()["version"]
    assert "password" not in str(response.json()).lower()
    assert "secret" not in str(response.json()).lower()


@pytest.mark.django_db
def test_cron_refuses_unauthenticated_requests(client, monkeypatch):
    monkeypatch.setenv("LEDGER_DEPLOYMENT", "vercel")
    monkeypatch.setenv("CRON_SECRET", "Z" * 44)
    with patch("ledger.cron_views.jobs.refresh_fx_rates") as fx:
        assert client.get("/api/internal/cron/daily").status_code == 403
        assert (
            client.get(
                "/api/internal/cron/daily",
                HTTP_AUTHORIZATION="Bearer incorrect",
            ).status_code
            == 403
        )
    fx.assert_not_called()


@pytest.mark.django_db
def test_cron_not_exposed_in_desktop_or_docker(client, monkeypatch):
    monkeypatch.delenv("LEDGER_DEPLOYMENT", raising=False)
    assert client.get("/api/internal/cron/daily").status_code == 404
