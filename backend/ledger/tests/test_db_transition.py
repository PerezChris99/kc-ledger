"""Database cutover must not hide populated legacy SQLite files."""

import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management.base import CommandError

from ledger.management.commands.check_db_transition import Command


def _populated_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE auth_user (id integer primary key)")
        connection.execute("INSERT INTO auth_user (id) VALUES (1)")


def test_cutover_refuses_legacy_sqlite_without_operator_confirmation(tmp_path, monkeypatch):
    legacy = tmp_path / "ledger.sqlite3"
    _populated_database(legacy)
    monkeypatch.setenv("LEDGER_DB_PATH", str(legacy))
    monkeypatch.delenv("LEDGER_SQLITE_MIGRATION_VERIFIED", raising=False)

    with (
        patch(
            "ledger.management.commands.check_db_transition.connection",
            SimpleNamespace(vendor="postgresql"),
        ),
        pytest.raises(CommandError, match="Migrate and reconcile"),
    ):
        Command().handle()


def test_cutover_requires_explicit_verified_flag_for_existing_data(tmp_path, monkeypatch):
    legacy = tmp_path / "ledger.sqlite3"
    _populated_database(legacy)
    monkeypatch.setenv("LEDGER_DB_PATH", str(legacy))
    monkeypatch.setenv("LEDGER_SQLITE_MIGRATION_VERIFIED", "1")
    with patch(
        "ledger.management.commands.check_db_transition.connection",
        SimpleNamespace(vendor="postgresql"),
    ):
        Command().handle()


def test_cutover_guard_does_not_block_sqlite_mode(tmp_path, monkeypatch):
    legacy = tmp_path / "ledger.sqlite3"
    _populated_database(legacy)
    monkeypatch.setenv("LEDGER_DB_PATH", str(legacy))
    with patch(
        "ledger.management.commands.check_db_transition.connection",
        SimpleNamespace(vendor="sqlite"),
    ):
        Command().handle()
