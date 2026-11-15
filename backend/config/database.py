"""Select the database before Django initializes its connection pool.

PostgreSQL is the normal authoritative store. Auto mode is intended for a
single-machine desktop: it selects once and pins that backend on disk so an
outage never silently creates an independent set of financial records.
"""

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)
POSTGRES = "django.db.backends.postgresql"
SQLITE = "django.db.backends.sqlite3"


def _sqlite_database(environ, base_dir):
    name = Path(environ.get("LEDGER_DB_PATH") or base_dir / "data" / "ledger.sqlite3")
    name = name.expanduser().resolve()
    name.parent.mkdir(parents=True, exist_ok=True)
    return {
        "ENGINE": SQLITE,
        "NAME": name,
        "OPTIONS": {"timeout": 20},
    }


def _postgres_database(environ):
    return {
        "ENGINE": POSTGRES,
        "NAME": environ.get("LEDGER_DB_NAME", "kc_ledger"),
        "USER": environ.get("LEDGER_DB_USER", "kc_ledger"),
        "PASSWORD": environ.get("LEDGER_DB_PASSWORD", ""),
        "HOST": environ.get("LEDGER_DB_HOST", "127.0.0.1"),
        "PORT": environ.get("LEDGER_DB_PORT", "5432"),
        "CONN_MAX_AGE": max(0, int(environ.get("LEDGER_DB_CONN_MAX_AGE", "60"))),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "connect_timeout": max(1, int(environ.get("LEDGER_DB_CONNECT_TIMEOUT", "3"))),
            "options": "-c statement_timeout=15000 -c idle_in_transaction_session_timeout=30000",
            "application_name": "kc_ledger",
        },
    }


def _reachable(postgres):
    import psycopg

    kwargs = {
        "dbname": postgres["NAME"],
        "user": postgres["USER"],
        "host": postgres["HOST"],
        "port": postgres["PORT"],
        "connect_timeout": postgres["OPTIONS"]["connect_timeout"],
        "application_name": "kc_ledger_startup",
    }
    if postgres["PASSWORD"]:
        kwargs["password"] = postgres["PASSWORD"]
    try:
        with psycopg.connect(**kwargs):
            return True
    except psycopg.OperationalError as exc:
        message = str(exc).lower()
        # Invalid credentials, missing roles/dbs, or certificate errors are
        # deployment errors: never silently treat them as an offline server.
        offline = any(
            marker in message
            for marker in (
                "connection refused",
                "connection timed out",
                "timeout expired",
                "network is unreachable",
                "no route to host",
                "could not translate host name",
                "name or service not known",
                "nodename nor servname provided",
            )
        )
        if not offline:
            raise RuntimeError(
                "PostgreSQL is reachable but its connection is invalid; "
                "check the database name, role, password and server security."
            ) from None
        return False


def _legacy_sqlite_has_data(path):
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
            return (
                db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='django_migrations'"
                ).fetchone()
                is not None
            )
    except sqlite3.DatabaseError:
        # Do not automatically switch away from a damaged legacy database.
        raise RuntimeError("Existing SQLite database is not readable; restore it first.") from None


def _pin_backend(marker, selected):
    """Create a durable first-choice marker exclusively, even under startup races."""
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        with marker.open("x", encoding="ascii") as handle:
            handle.write(selected + "\n")
        try:
            marker.chmod(0o600)
        except OSError:
            pass
    except FileExistsError:
        existing = marker.read_text(encoding="ascii").strip()
        if existing != selected:
            # A competing startup selected another backend: fail closed.
            raise RuntimeError(
                "Concurrent KC Ledger startup selected different databases. "
                "Stop all instances and resolve the backend pin before restarting."
            ) from None


def select_database(environ=None, base_dir=None):
    env = os.environ if environ is None else environ
    base = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent.parent
    mode = env.get("LEDGER_DB_ENGINE", "postgres").strip().lower()
    if mode not in {"postgres", "postgresql", "sqlite", "auto"}:
        raise RuntimeError("LEDGER_DB_ENGINE must be postgres, sqlite or auto.")
    sqlite = _sqlite_database(env, base)
    if mode == "sqlite":
        return sqlite
    postgres = _postgres_database(env)
    if mode != "auto":
        return postgres

    marker = (
        Path(env.get("LEDGER_DB_PIN_PATH") or sqlite["NAME"].parent / ".ledger-db-backend")
        .expanduser()
        .resolve()
    )
    if marker.exists():
        selected = marker.read_text(encoding="ascii").strip()
        if selected not in {"postgres", "sqlite"}:
            raise RuntimeError("Invalid database pin. Stop and inspect the application data.")
        if selected == "postgres" and not _reachable(postgres):
            raise RuntimeError(
                "PostgreSQL was previously selected and is now unavailable. "
                "Refusing a silent SQLite failover that would split financial data."
            )
        return postgres if selected == "postgres" else sqlite

    if _legacy_sqlite_has_data(sqlite["NAME"]):
        selected = "sqlite"
        logger.warning("Existing SQLite ledger detected; retaining its database until migrated.")
    elif _reachable(postgres):
        selected = "postgres"
    elif env.get("LEDGER_ALLOW_SQLITE_FALLBACK", "0").lower() in {"1", "true", "yes"}:
        selected = "sqlite"
        logger.warning(
            "PostgreSQL is offline; using pinned SQLite fallback. "
            "Data will not automatically switch when PostgreSQL returns."
        )
    else:
        raise RuntimeError(
            "Local PostgreSQL is unavailable. Start PostgreSQL or explicitly enable "
            "SQLite fallback with LEDGER_DB_ENGINE=auto and LEDGER_ALLOW_SQLITE_FALLBACK=1."
        )

    _pin_backend(marker, selected)
    return postgres if selected == "postgres" else sqlite
