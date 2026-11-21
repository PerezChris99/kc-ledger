"""Protected, backed-up production migration before Vercel alias promotion."""

import os
import hashlib
import re
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
    # Prisma Postgres and other PgBouncer providers need a DIRECT session
    # endpoint for schema migrations and pg_dump. Vercel runtime keeps using
    # the pooled DATABASE_URL for API/cron requests.
    runtime_url = os.environ.get("DATABASE_URL", "")
    direct_url = os.environ.get("DATABASE_DIRECT_URL", "")
    if "pooled.db.prisma.io" in runtime_url and not direct_url:
        raise SystemExit("Prisma Postgres requires DATABASE_DIRECT_URL for migrations and pg_dump.")
    if direct_url:
        os.environ["DATABASE_URL"] = direct_url
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
    archives = list(backup_dir.glob("ledger-*.dump"))
    if len(archives) != 1:
        raise SystemExit("Exactly one verified predeploy archive must be present")
    archive = archives[0]
    # A runner-only backup disappears at workflow end. Production requires a
    # durable PRIVATE offsite copy, server-side KMS encryption and OIDC identity.
    backup_bucket = os.environ.get("LEDGER_BACKUP_S3_URI", "")
    kms_key = os.environ.get("LEDGER_BACKUP_KMS_KEY_ID", "")
    if not re.fullmatch(r"s3://[a-z0-9][a-z0-9.-]{2,62}/[a-zA-Z0-9/_-]+/?", backup_bucket) or not kms_key:
        raise SystemExit("Secure S3 backup destination and KMS key must be configured")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    destination = backup_bucket.rstrip("/") + "/" + archive.name
    subprocess.run(
        [
            "aws", "s3", "cp", str(archive), destination,
            "--sse", "aws:kms", "--sse-kms-key-id", kms_key,
            "--metadata", "sha256=" + sha, "--no-progress",
        ],
        check=True, env=os.environ.copy(), capture_output=True,
    )
    # Verify remote metadata before any migration alters the live database.
    from urllib.parse import urlsplit

    parsed = urlsplit(destination)
    result = subprocess.run(
        [
            "aws", "s3api", "head-object", "--bucket", parsed.netloc,
            "--key", parsed.path.lstrip("/"), "--query", "Metadata.sha256",
            "--output", "text",
        ],
        check=True, env=os.environ.copy(), capture_output=True, text=True,
    )
    if result.stdout.strip() != sha:
        raise SystemExit("Uploaded production backup SHA does not match")
    run("migrate", "--noinput")
    run("ensure_owner")
    run("check_db_transition")


if __name__ == "__main__":
    main()
