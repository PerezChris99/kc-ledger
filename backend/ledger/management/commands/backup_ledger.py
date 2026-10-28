import os
import sqlite3
from datetime import date
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

class Command(BaseCommand):
    help = "Create and integrity-check a consistent SQLite backup using the online backup API."

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("This backup command is intended for the configured SQLite database.")
        connection.ensure_connection()
        source = connection.connection
        if source is None:
            raise CommandError("Database connection could not be opened.")
        backup_dir = Path(os.environ.get("LEDGER_BACKUP_DIR", "/app/data/backups"))
        backup_dir.mkdir(parents=True, exist_ok=True)
        destination = backup_dir / f"ledger-{date.today().isoformat()}.sqlite3"
        try:
            with sqlite3.connect(destination) as target:
                source.backup(target)
                result = target.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise CommandError(f"Backup integrity check failed: {result}")
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise CommandError(f"Backup failed: {exc}") from exc
        backups = sorted(backup_dir.glob("ledger-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
        for old in backups[14:]:
            old.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Backup verified: {destination}"))
