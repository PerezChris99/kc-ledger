"""PostgreSQL backup and restore primitives using official client tools.

Use matching pg_dump/pg_restore versions for the running server. Passwords are
passed via environment, never through argv, logs or a shell command.
"""

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from django.core.management.base import CommandError
from django.db import connection


def _executable(name):
    configured = os.environ.get("LEDGER_PG_BIN", "").strip()
    if configured:
        path = Path(configured) / (name + (".exe" if os.name == "nt" else ""))
        if not path.is_file():
            raise CommandError(f"{name} not found under LEDGER_PG_BIN.")
        return str(path)
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        root = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "PostgreSQL"
        if root.is_dir():
            for version in sorted(root.iterdir(), reverse=True):
                candidate = version / "bin" / (name + ".exe")
                if candidate.is_file():
                    return str(candidate)
    raise CommandError(
        f"{name} is not installed or not on PATH. Install matching PostgreSQL "
        "client tools, or configure LEDGER_PG_BIN."
    )


def _connection_args():
    settings = connection.settings_dict
    env = os.environ.copy()
    env["PGCONNECT_TIMEOUT"] = str(settings.get("OPTIONS", {}).get("connect_timeout", 3))
    if settings.get("PASSWORD"):
        env["PGPASSWORD"] = settings["PASSWORD"]
    args = [
        "--host",
        settings.get("HOST") or "127.0.0.1",
        "--port",
        str(settings.get("PORT") or 5432),
        "--username",
        settings["USER"],
        "--dbname",
        settings["NAME"],
        "--no-password",
    ]
    return args, env


def _run(name, args, *, env):
    result = subprocess.run(
        [_executable(name), *args],
        env=env,
        check=False,
        capture_output=True,
        timeout=180,
    )
    if result.returncode != 0:
        # Never print pgpass/connection details in application logs.
        raise CommandError(
            f"{name} failed. Verify PostgreSQL credentials, privileges, "
            "client-server version compatibility and database availability."
        )


def validate_dump(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise CommandError("PostgreSQL backup file is missing or empty.")
    _run("pg_restore", ["--list", str(path)], env=os.environ.copy())


def write_postgres_backup(destination):
    """Create a pg_dump custom archive; validate before installing atomically."""
    directory = destination.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".kc-ledger-pg-", suffix=".dump", dir=str(directory))
    os.close(fd)
    staged = Path(temporary)
    try:
        args, env = _connection_args()
        _run(
            "pg_dump",
            [*args, "--format=custom", "--no-owner", "--no-acl", "--file", str(staged)],
            env=env,
        )
        validate_dump(staged)
        try:
            staged.chmod(0o600)
        except OSError:
            pass
        os.replace(staged, destination)
        return destination
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CommandError("PostgreSQL backup failed or exceeded its timeout.") from exc
    finally:
        staged.unlink(missing_ok=True)


def restore_postgres_dump(path):
    """Apply a validated archive as a single transaction (application offline)."""
    validate_dump(path)
    args, env = _connection_args()
    try:
        _run(
            "pg_restore",
            [
                *args,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-acl",
                "--single-transaction",
                "--exit-on-error",
                str(path),
            ],
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CommandError("PostgreSQL restore failed or exceeded its timeout.") from exc


def pre_restore_backup(directory):
    path = directory / ("pre-restore-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".dump")
    return write_postgres_backup(path)
