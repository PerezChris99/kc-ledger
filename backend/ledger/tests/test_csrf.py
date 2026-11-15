"""Browser CSRF regression tests using Django's real CSRF test client."""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client


@pytest.mark.django_db
def test_login_requires_csrf_even_before_authentication():
    browser = Client(enforce_csrf_checks=True)
    payload = {"username": "nonexistent", "password": "wrong"}
    unprotected = browser.post("/api/auth/login", data=payload, content_type="application/json")
    assert unprotected.status_code == 403
    token = browser.get("/api/csrf").json()["csrfToken"]
    protected = browser.post(
        "/api/auth/login", data=payload, content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert protected.status_code == 401


@pytest.mark.django_db
def test_staff_authenticated_mutations_require_csrf():
    browser = Client(enforce_csrf_checks=True)
    user = get_user_model().objects.create_user(
        username="csrf-owner", password="long-password-12345", is_staff=True
    )
    browser.force_login(user)
    payload = {
        "name": "CSRF Target", "type": "revenue", "amount": "100.00",
        "currency": "USD", "deadline": "2027-01-01",
    }
    response = browser.post("/api/targets", data=payload, content_type="application/json")
    assert response.status_code == 403
    token = browser.get("/api/csrf").json()["csrfToken"]
    valid = browser.post(
        "/api/targets", data=payload, content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert valid.status_code == 200
