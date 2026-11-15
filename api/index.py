"""Vercel Python WSGI function; no embedded scheduler or local SQLite storage."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["LEDGER_DEPLOYMENT"] = "vercel"
os.environ["LEDGER_DB_ENGINE"] = "postgres"
os.environ["RUN_SCHEDULER"] = "0"

from config.wsgi import application as app  # noqa: E402
