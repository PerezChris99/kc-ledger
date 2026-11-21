"""Database selection, safety pinning and SQLite fallback tests."""

from unittest.mock import patch

import pytest
from config.database import POSTGRES, SQLITE, select_database


def _env(tmp_path, **override):
    return {
        "LEDGER_DB_PATH": str(tmp_path / "ledger.sqlite3"),
        "LEDGER_DB_PIN_PATH": str(tmp_path / ".db-backend"),
        **override,
    }


def test_postgres_is_default_and_uses_short_timeouts(tmp_path):
    config = select_database(_env(tmp_path), tmp_path)
    assert config["ENGINE"] == POSTGRES
    assert config["HOST"] == "127.0.0.1"
    assert config["PORT"] == "5432"
    assert config["CONN_MAX_AGE"] == 60
    assert config["CONN_HEALTH_CHECKS"] is True
    assert config["OPTIONS"]["connect_timeout"] == 3


def test_sqlite_mode_is_explicit_fallback(tmp_path):
    db = select_database(_env(tmp_path, LEDGER_DB_ENGINE="sqlite"), tmp_path)
    assert db["ENGINE"] == SQLITE
    assert db["NAME"].parent.exists()


def test_auto_prefers_postgres_and_pins_it(tmp_path):
    env = _env(tmp_path, LEDGER_DB_ENGINE="auto", LEDGER_ALLOW_SQLITE_FALLBACK="1")
    with patch("config.database._reachable", return_value=True):
        db = select_database(env, tmp_path)
    assert db["ENGINE"] == POSTGRES
    assert (tmp_path / ".db-backend").read_text().strip() == "postgres"
    with (
        patch("config.database._reachable", return_value=False),
        pytest.raises(RuntimeError, match="Refusing a silent SQLite failover"),
    ):
        select_database(env, tmp_path)


def test_auto_sqlite_fallback_is_pinned_across_recovery(tmp_path):
    env = _env(tmp_path, LEDGER_DB_ENGINE="auto", LEDGER_ALLOW_SQLITE_FALLBACK="1")
    with patch("config.database._reachable", return_value=False):
        db = select_database(env, tmp_path)
    assert db["ENGINE"] == SQLITE
    with patch("config.database._reachable", return_value=True) as reach:
        assert select_database(env, tmp_path)["ENGINE"] == SQLITE
    reach.assert_not_called()
    assert (tmp_path / ".db-backend").read_text().strip() == "sqlite"


def test_auto_without_fallback_fails_closed(tmp_path):
    with (
        patch("config.database._reachable", return_value=False),
        pytest.raises(RuntimeError, match="Start PostgreSQL"),
    ):
        select_database(_env(tmp_path, LEDGER_DB_ENGINE="auto"), tmp_path)
    assert not (tmp_path / ".db-backend").exists()


def test_auto_does_not_discard_existing_legacy_sqlite_database(tmp_path):
    import sqlite3

    path = tmp_path / "ledger.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE django_migrations (id integer primary key)")
    with patch("config.database._reachable") as reach:
        db = select_database(
            _env(tmp_path, LEDGER_DB_ENGINE="auto", LEDGER_ALLOW_SQLITE_FALLBACK="1"),
            tmp_path,
        )
    assert db["ENGINE"] == SQLITE
    reach.assert_not_called()


def test_invalid_engine_is_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="LEDGER_DB_ENGINE"):
        select_database(_env(tmp_path, LEDGER_DB_ENGINE="mysql"), tmp_path)


def test_pinning_race_fails_closed(tmp_path):
    marker = tmp_path / ".db-backend"
    marker.write_text("sqlite\n")
    from config.database import _pin_backend

    with pytest.raises(RuntimeError, match="different databases"):
        _pin_backend(marker, "postgres")


def test_vercel_postgres_does_not_create_sqlite_directories(tmp_path):
    database_dir = tmp_path / "readonly-install" / "uncreated"
    config = select_database(
        _env(
            tmp_path,
            LEDGER_DEPLOYMENT="vercel",
            LEDGER_DB_ENGINE="postgres",
            DATABASE_URL="postgres://kc:password@pooled.db.prisma.io:5432/postgres?sslmode=require",
        ),
        database_dir,
    )
    assert config["ENGINE"] == POSTGRES
    assert config["HOST"] == "pooled.db.prisma.io"
    assert not (database_dir / "data").exists()
    assert "options" not in config["OPTIONS"]
    assert config["CONN_MAX_AGE"] == 0


@pytest.mark.parametrize("mode", ["disable", "allow", "prefer"])
def test_vercel_rejects_insecure_transport(tmp_path, mode):
    with pytest.raises(RuntimeError, match="TLS"):
        select_database(
            _env(
                tmp_path,
                LEDGER_DEPLOYMENT="vercel",
                DATABASE_URL=f"postgres://kc:pw@db.prisma.io:5432/postgres?sslmode={mode}",
            ),
            tmp_path,
        )


def test_postgres_direct_endpoint_can_keep_session_timeouts(tmp_path):
    config = select_database(
        _env(
            tmp_path,
            LEDGER_DEPLOYMENT="vercel",
            DATABASE_URL="postgresql://kc:pw@db.prisma.io:5432/postgres?sslmode=verify-full",
        ),
        tmp_path,
    )
    assert config["OPTIONS"]["sslmode"] == "verify-full"
    assert "statement_timeout" in config["OPTIONS"]["options"]
