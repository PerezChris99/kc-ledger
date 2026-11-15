"""Explicit database health probe: no credentials or private data in output."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Check the configured KC Ledger database connection and backend."

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone()[0] != 1:
                    raise CommandError("Database connection check returned an invalid result.")
        except Exception as exc:
            raise CommandError(
                "Unable to connect to the configured database; check server, credentials and network."
            ) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"KC Ledger database ready: {connection.vendor}, "
                f"name={connection.settings_dict['NAME']}, "
                f"host={connection.settings_dict.get('HOST') or 'local'}"
            )
        )
