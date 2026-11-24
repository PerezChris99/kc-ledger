from time import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from .backup_ledger import backup_locations, check_integrity, validate_dump


def recent_snapshot(hours):
    directory, secondary = backup_locations()
    suffix = ".sqlite3" if connection.vendor == "sqlite" else ".dump"
    cutoff = time() - hours * 3600
    for snapshot in sorted(directory.glob(f"ledger-*{suffix}"), reverse=True):
        if snapshot.stat().st_mtime < cutoff:
            continue
        if secondary and not (secondary / snapshot.name).is_file():
            continue
        return snapshot
    return None


class Command(BaseCommand):
    help = (
        "Check freshness and readability of the latest primary and configured secondary snapshot."
    )

    def add_arguments(self, parser):
        parser.add_argument("--max-hours", type=int, default=26)

    def handle(self, *args, **options):
        snapshot = recent_snapshot(options["max_hours"])
        if not snapshot:
            raise CommandError("Backup missing or overdue.")
        verify = check_integrity if connection.vendor == "sqlite" else validate_dump
        verify(snapshot)
        _, secondary = backup_locations()
        if secondary:
            verify(secondary / snapshot.name)
        self.stdout.write(f"Backup checked: {snapshot.name}")
