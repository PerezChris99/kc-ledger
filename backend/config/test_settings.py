"""Test-only Django settings. Default tests use isolated SQLite.

PostgreSQL tests are selected explicitly with LEDGER_DB_ENGINE=postgres.
"""

import os
import secrets

os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(64))
os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ.setdefault("LEDGER_DB_ENGINE", "sqlite")

from .settings import *

DEBUG = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
