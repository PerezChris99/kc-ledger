from ninja.security import django_auth_is_staff

# Django Ninja's cookie-backed staff session auth enforces CSRF for mutations.
# A plain callable auth class would inadvertently bypass CSRF in Ninja 1.8.
staff_session_auth = django_auth_is_staff


from datetime import timedelta
from hashlib import sha256

from django.conf import settings
from django.db.models import F
from django.utils import timezone


def throttle_key(remote: str, username: str) -> str:
    return sha256((remote + ":" + username.strip().casefold()).encode("utf-8")).hexdigest()


def is_login_blocked(key: str) -> bool:
    from ledger.models import LoginThrottle

    now = timezone.now()
    return LoginThrottle.objects.filter(key=key, locked_until__gt=now).exists()


def record_failed_login(key: str) -> None:
    """Use atomic SQL increments, retaining lockouts across server restarts."""
    from ledger.models import LoginThrottle

    now = timezone.now()
    window = timedelta(seconds=getattr(settings, "LEDGER_LOGIN_WINDOW_SECONDS", 900))
    limit = getattr(settings, "LEDGER_LOGIN_MAX_ATTEMPTS", 5)
    LoginThrottle.objects.get_or_create(key=key, defaults={"window_started_at": now})
    LoginThrottle.objects.filter(key=key, window_started_at__lt=now - window).update(
        attempts=0, window_started_at=now, locked_until=None
    )
    LoginThrottle.objects.filter(key=key).update(attempts=F("attempts") + 1)
    LoginThrottle.objects.filter(key=key, attempts__gte=limit).update(locked_until=now + window)


def clear_login_throttle(key: str) -> None:
    from ledger.models import LoginThrottle

    LoginThrottle.objects.filter(key=key).delete()
