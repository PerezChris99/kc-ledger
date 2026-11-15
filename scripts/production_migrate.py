"""Protected, backed-up production migration before Vercel alias promotion."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


def main():
    candidate = Path(".vercel/.env.production.local")
    if not candidate.is_file():
        raise SystemExit("Vercel production environment has not been pulled")
    for key, value in dotenv_values(candidate).items():
        if value is not None:
            os.environ[key] = value
    os.environ["LEDGER_DEPLOYMENT"] = "vercel"
    os.environ["LEDGER_DB_ENGINE"] = "postgres"
    os.environ["RUN_SCHEDULER"] = "0"
    required = ("DATABASE_URL", "DJANGO_SECRET_KEY", "LEDGER_USERNAME", "LEDGER_PASSWORD")
    if any(not os.environ.get(name) for name in required):
        raise SystemExit("Missing production managed PostgreSQL or owner credentials")

    def run(*args):
        subprocess.run(
            [sys.executable, "backend/manage.py", *args],
            check=True, env=os.environ.copy()
        )

    run("db_status")
    run("check", "--database", "default")
    run("makemigrations", "--check", "--dry-run")
    # Before any schema update, create a verified PostgreSQL backup in the
    # restricted ephemeral runner. Never upload it as a workflow artifact.
    backup_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "kc-ledger-predeploy"
    run("backup_ledger", "--directory", str(backup_dir))
    if not list(backup_dir.glob("ledger-*.dump")):
        raise SystemExit("Pre-migration PostgreSQL backup missing; refusing deployment")
    run("migrate", "--noinput")
    run("ensure_owner")
    run("check_db_transition")


if __name__ == "__main__":
    main()
