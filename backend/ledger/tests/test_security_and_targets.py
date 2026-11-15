"""Security and target persistence regressions."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from ledger.models import LoginThrottle, Target


@pytest.mark.django_db
def test_login_throttle_persists_when_cache_is_cleared(client):
    from django.core.cache import cache

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            data={"username": "unknown-account", "password": "wrong-password"},
            content_type="application/json",
        )
        assert response.status_code == 401
    cache.clear()
    response = client.post(
        "/api/auth/login",
        data={"username": "unknown-account", "password": "wrong-password"},
        content_type="application/json",
    )
    assert response.status_code == 429
    assert LoginThrottle.objects.count() == 1


@pytest.mark.django_db
def test_successful_login_resets_persistent_throttle(client):
    user = get_user_model().objects.create_user(
        username="owner", password="correct-strong-password", is_staff=True
    )
    for _ in range(2):
        response = client.post(
            "/api/auth/login",
            data={"username": user.username, "password": "wrong"},
            content_type="application/json",
        )
        assert response.status_code == 401
    response = client.post(
        "/api/auth/login",
        data={"username": user.username, "password": "correct-strong-password"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert not LoginThrottle.objects.exists()


@pytest.mark.django_db
def test_login_throttle_resets_outdated_window(client):
    from ledger.security import throttle_key

    key = throttle_key("127.0.0.1", "expired")
    LoginThrottle.objects.create(
        key=key,
        attempts=5,
        window_started_at=timezone.now() - timedelta(hours=1),
        locked_until=timezone.now() - timedelta(minutes=30),
    )
    response = client.post(
        "/api/auth/login",
        data={"username": "expired", "password": "wrong"},
        content_type="application/json",
    )
    assert response.status_code == 401
    row = LoginThrottle.objects.get(key=key)
    assert row.attempts == 1


@pytest.fixture
def owner_client(client):
    user = get_user_model().objects.create_user(
        username="target-owner", password="long-password-123456", is_staff=True
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_target_patch_persists_and_archive_soft_deletes(owner_client):
    target = Target.objects.create(
        name="Revenue",
        type=Target.Type.REVENUE,
        amount=Decimal("100.00"),
        currency="USD",
        deadline=date.today() + timedelta(days=40),
    )
    edited = owner_client.patch(
        f"/api/targets/{target.pk}",
        data={
            "name": "Updated revenue",
            "type": "revenue",
            "amount": "200.00",
            "currency": "UGX",
            "deadline": (date.today() + timedelta(days=30)).isoformat(),
        },
        content_type="application/json",
    )
    assert edited.status_code == 200
    target.refresh_from_db()
    assert target.name == "Updated revenue"
    assert target.currency == "UGX"
    archived = owner_client.delete(f"/api/targets/{target.pk}")
    assert archived.status_code == 200
    assert not Target.objects.filter(pk=target.pk).exists()
    assert Target.all_objects.filter(pk=target.pk, deleted_at__isnull=False).exists()
