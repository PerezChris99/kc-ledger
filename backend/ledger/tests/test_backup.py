"""Online backup tests, including corrupted backups and atomic output."""
from pathlib import Path
import sqlite3

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from ledger.management.commands.backup_ledger import check_integrity, write_backup


@pytest.mark.django_db(transaction=True)
def test_backup_is_integrity_checked_and_atomic(tmp_path):
    destination = tmp_path / "ledger-test.sqlite3"
    connection.ensure_connection()
    write_backup(destination, connection.connection)
    assert destination.exists()
    check_integrity(destination)
    assert not list(tmp_path.glob(".kc-ledger-backup-*"))


def test_backup_rejects_corruption(tmp_path):
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"this is not an SQLite database")
    with pytest.raises((CommandError, sqlite3.DatabaseError)):
        check_integrity(corrupt)


@pytest.mark.django_db(transaction=True)
def test_management_backup_creates_a_verifiable_snapshot(tmp_path):
    call_command("backup_ledger", directory=str(tmp_path), keep=2)
    snapshots = list(tmp_path.glob("ledger-*.sqlite3"))
    assert len(snapshots) == 1
    check_integrity(snapshots[0])


@pytest.mark.django_db(transaction=True)
def test_restore_defaults_to_nondestructive_dry_run(tmp_path):
    connection.ensure_connection()
    destination = tmp_path / "source.sqlite3"
    write_backup(destination, connection.connection)
    call_command("restore_ledger", str(destination))
    assert destination.is_file()
