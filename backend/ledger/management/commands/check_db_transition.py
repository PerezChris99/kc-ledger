"""Prevent a new PostgreSQL connection from hiding existing SQLite ledger data."""

import os
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Refuse accidental empty PostgreSQL cutover when legacy SQLite contains data."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            return
        legacy = Path(
            os.environ.get("LEDGER_DB_PATH")
            or settings.BASE_DIR / "data" / "ledger.sqlite3"
        ).expanduser().resolve()
        if not legacy.is_file() or not legacy.stat().st_size:
            return
        try:
            with sqlite3.connect(f"file:{legacy.as_posix()}?mode=ro", uri=True) as db:
                tables = {
                    name for (name,) in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                populated = [
                    name for name in ("auth_user", "ledger_client", "ledger_invoice", "ledger_payment")
                    if name in tables and db.execute(
                        f'SELECT 1 FROM "{name}" LIMIT 1'
                    ).fetchone() is not None
                ]
        except sqlite3.Error as exc:
            raise CommandError(
                "A legacy SQLite ledger exists but cannot be checked. "
                "Preserve the file and investigate before enabling PostgreSQL."
            ) from exc
        if populated and os.environ.get("LEDGER_SQLITE_MIGRATION_VERIFIED") != "1":
            raise CommandError(
                "Existing SQLite ledger data detected. Starting PostgreSQL would make "
                "those records appear to vanish. Migrate and reconcile the data first, "
                "then explicitly set LEDGER_SQLITE_MIGRATION_VERIFIED=1."
            )
