"""Verified atomic SQLite backups with configurable retention and secondary copy."""

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from ledger.pg_backup import validate_dump, write_postgres_backup


def check_integrity(path: Path) -> None:
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as handle:
        row = handle.execute("PRAGMA integrity_check").fetchone()
    if not row or row[0] != "ok":
        raise CommandError(f"Database integrity check failed: {path}")


def write_backup(destination: Path, source_connection) -> Path:
    """Write a consistent snapshot then atomically install it into its final path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".kc-ledger-backup-", suffix=".sqlite3", dir=str(destination.parent)
    )
    os.close(fd)
    temporary_path = Path(temporary)
    try:
        with sqlite3.connect(str(temporary_path), timeout=30) as target:
            source_connection.backup(target)
        check_integrity(temporary_path)
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass
        os.replace(temporary_path, destination)
        return destination
    finally:
        temporary_path.unlink(missing_ok=True)


def copy_secondary(source: Path, directory: Path, verify=check_integrity) -> Path:
    """Copy the verified snapshot off the primary volume, atomically."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / source.name
    fd, temp = tempfile.mkstemp(prefix=".kc-ledger-copy-", suffix=".sqlite3", dir=str(directory))
    os.close(fd)
    temporary = Path(temp)
    try:
        shutil.copyfile(source, temporary)
        verify(temporary)
        os.replace(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def backup_locations(directory=None):
    sqlite = connection.vendor == "sqlite"
    default_dir = (
        Path(connection.settings_dict["NAME"]).parent / "backups"
        if sqlite
        else settings.BASE_DIR / "data" / "backups"
    )
    backup_dir = (
        Path(directory or os.environ.get("LEDGER_BACKUP_DIR") or default_dir).expanduser().resolve()
    )
    secondary = os.environ.get("LEDGER_SECONDARY_BACKUP_DIR", "").strip()
    secondary_path = Path(secondary).expanduser().resolve() if secondary else None
    if secondary_path and secondary_path == backup_dir:
        raise CommandError("Secondary backup location must differ from primary.")

    return backup_dir, secondary_path


class Command(BaseCommand):
    help = "Back up the live SQLite database via its online API and verify the backup."

    def add_arguments(self, parser):
        parser.add_argument("--directory", default=None, help="Primary backup directory")
        parser.add_argument("--keep", type=int, default=14, help="Number of backups to retain")

    def handle(self, *args, **options):
        if connection.vendor not in {"sqlite", "postgresql"}:
            raise CommandError("Unsupported KC Ledger backup backend.")
        if options["keep"] < 1 or options["keep"] > 1000:
            raise CommandError("--keep must be between 1 and 1000.")
        sqlite = connection.vendor == "sqlite"
        backup_dir, secondary_path = backup_locations(options["directory"])

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        if sqlite:
            connection.ensure_connection()
            if connection.connection is None:
                raise CommandError("No open SQLite connection.")
            filename = f"ledger-{timestamp}.sqlite3"
            destination = write_backup(backup_dir / filename, connection.connection)
            verify = check_integrity
        else:
            filename = f"ledger-{timestamp}.dump"
            destination = write_postgres_backup(backup_dir / filename)
            verify = validate_dump

        if secondary_path:
            copy_secondary(destination, secondary_path, verify=verify)
        backups = sorted(
            backup_dir.glob("ledger-*" + (".sqlite3" if sqlite else ".dump")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in backups[options["keep"] :]:
            old.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Backup verified: {destination}"))
