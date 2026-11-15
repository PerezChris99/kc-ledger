"""Offline SQLite restore with verification and a pre-restore safety snapshot."""

import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from ledger.pg_backup import pre_restore_backup, restore_postgres_dump, validate_dump

from ledger.management.commands.backup_ledger import check_integrity, write_backup


class Command(BaseCommand):
    help = "Validate a snapshot, then optionally restore it while KC Ledger is stopped."

    def add_arguments(self, parser):
        parser.add_argument("backup", type=Path, help="Verified .sqlite3 snapshot")
        parser.add_argument(
            "--apply", action="store_true", help="Apply the restore (default dry-run)"
        )
        parser.add_argument("--confirm", default="", help="Must equal RESTORE-LEDGER to apply")

    def handle(self, *args, **options):
        if connection.vendor == "postgresql":
            return self.restore_postgresql(options)
        if connection.vendor != "sqlite":
            raise CommandError("Unsupported KC Ledger restore backend.")
        backup = options["backup"].expanduser().resolve()
        if not backup.is_file():
            raise CommandError(f"Backup not found: {backup}")
        try:
            check_integrity(backup)
        except (OSError, sqlite3.Error) as exc:
            raise CommandError(f"Backup is not usable: {exc}") from exc
        database = Path(connection.settings_dict["NAME"]).resolve()
        if backup == database:
            raise CommandError("Cannot restore the active database from itself.")
        if not options["apply"]:
            self.stdout.write(
                f"DRY RUN: valid backup {backup}; target database {database}. "
                "Stop the application, then pass --apply --confirm RESTORE-LEDGER."
            )
            return
        if options["confirm"] != "RESTORE-LEDGER":
            raise CommandError("--apply requires --confirm RESTORE-LEDGER.")
        database.parent.mkdir(parents=True, exist_ok=True)
        safety = None
        if database.exists():
            connection.ensure_connection()
            live = connection.connection
            if live is None:
                raise CommandError("Unable to open target database for safety backup.")
            backup_dir = database.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            safety = write_backup(
                backup_dir
                / ("pre-restore-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3"),
                live,
            )
            with connection.cursor() as cursor:
                busy, *_ = cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if busy:
                raise CommandError(
                    "Database is busy. Stop all running KC Ledger processes before restoring."
                )
            connection.close()

        fd, temp = tempfile.mkstemp(
            prefix=".kc-ledger-restore-", suffix=".sqlite3", dir=str(database.parent)
        )
        os.close(fd)
        staged = Path(temp)
        try:
            with (
                sqlite3.connect(str(backup), timeout=30) as src,
                sqlite3.connect(str(staged), timeout=30) as dest,
            ):
                src.backup(dest)
            check_integrity(staged)
            os.replace(staged, database)
            for suffix in ("-wal", "-shm"):
                (database.parent / (database.name + suffix)).unlink(missing_ok=True)
            check_integrity(database)
        except Exception as exc:
            if safety and safety.exists():
                os.replace(safety, database)
            raise CommandError(
                f"Restore failed; previous state preserved if possible: {exc}"
            ) from exc
        finally:
            staged.unlink(missing_ok=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"Restored and verified: {database}."
                + (f" Safety backup retained at {safety}." if safety else "")
            )
        )

    def restore_postgresql(self, options):
        """Validate a pg_dump archive; apply only after an offline safety dump."""
        backup = options["backup"].expanduser().resolve()
        validate_dump(backup)
        if not options["apply"]:
            self.stdout.write(
                f"DRY RUN: valid PostgreSQL archive {backup}; "
                "stop KC Ledger, then pass --apply --confirm RESTORE-LEDGER."
            )
            return
        if options["confirm"] != "RESTORE-LEDGER":
            raise CommandError("--apply requires --confirm RESTORE-LEDGER.")
        backup_dir = Path(
            os.environ.get("LEDGER_BACKUP_DIR")
            or settings.BASE_DIR / "data" / "backups"
        ).expanduser().resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        safety = pre_restore_backup(backup_dir)
        # The application must be offline; do not allow this command to retain
        # a DB connection while pg_restore replaces schema objects.
        connection.close()
        restore_postgres_dump(backup)
        self.stdout.write(
            self.style.SUCCESS(
                f"PostgreSQL restored from {backup}. Pre-restore copy retained at {safety}."
            )
        )
