"""Test-only Django settings; never used in production.

Generate a unique ephemeral key rather than shipping a reusable test secret.
"""

import os
import secrets

os.environ.setdefault("DJANGO_SECRET_KEY", secrets.token_urlsafe(64))
os.environ.setdefault("DJANGO_DEBUG", "1")

from .settings import *

DEBUG = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
