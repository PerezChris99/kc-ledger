"""Reusable Django HTTP fixture for PDF and report integration tests."""

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def staff_client(client, db):
    owner = get_user_model().objects.create_user(
        username="report-owner", password="strong-test-password-123", is_staff=True
    )
    client.force_login(owner)
    return client
