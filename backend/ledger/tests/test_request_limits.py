"""Protect the API from unbounded local and proxied requests."""
import pytest


@pytest.mark.django_db
def test_long_query_rejected_before_dispatch(client):
    response = client.get("/api/health?" + "a=" + "x" * 4096)
    assert response.status_code == 414


@pytest.mark.django_db
def test_oversized_body_rejected_before_authentication(client):
    response = client.post(
        "/api/auth/login", data={"username": "u", "password": "x" * 1_048_577},
        content_type="application/json",
    )
    assert response.status_code == 413


@pytest.mark.django_db
def test_normal_health_request_allowed(client):
    response = client.get("/api/health")
    assert response.status_code == 200
