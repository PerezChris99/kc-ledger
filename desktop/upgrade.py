"""Offline upgrade checkpoint and post-install verification.

Inno Setup calls these commands before/after replacing binaries. No external
data files, backend pins or owner secrets are copied into the install folder.
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG = logging.getLogger("kc-ledger.upgrade")


def locations():
    root = Path(os.environ["LOCALAPPDATA"]) / "KCLedger"
    return root, root / "rollback", root / "rollback" / "previous-program"


def _logger():
    root, _, _ = locations()
    path = root / "logs"
    path.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        path / "update.log", maxBytes=2_000_000, backupCount=4, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)


def _django():
    root, _, _ = locations()
    from dotenv import load_dotenv

    load_dotenv(root / ".env", override=False)
    home = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(home))
    sys.path.insert(0, str(home / "backend"))
    os.environ.update({
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_SECRET_KEY": (root / ".session-key").read_text(encoding="utf-8").strip(),
        "DJANGO_DEBUG": "0", "LEDGER_DESKTOP": "1",
        "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "LEDGER_DB_PATH": str(root / "ledger.sqlite3"),
        "LEDGER_DB_PIN_PATH": str(root / ".database-backend"),
        "RUN_SCHEDULER": "0",
        "COOKIE_SECURE": "0",
        "LEDGER_BACKUP_DIR": str(root / "backups"),
    })
    os.environ.setdefault("LEDGER_DB_ENGINE", "auto")
    os.environ.setdefault("LEDGER_ALLOW_SQLITE_FALLBACK", "1")
    import django

    django.setup()


def prepare():
    """Called from OLD binary while it is stopped, before installer copies files."""
    _logger()
    root, rollback, previous = locations()
    program = Path(sys.executable).resolve().parent
    rollback.mkdir(parents=True, exist_ok=True)
    # Copy binaries to a secondary per-user directory before touching the install.
    staged = rollback / "previous-program.tmp"
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(program, staged)
    if previous.exists():
        shutil.rmtree(previous)
    os.replace(staged, previous)
    _django()
    from django.core.management import call_command
    from django.db import connection

    backup_dir = rollback / "database"
    backup_dir.mkdir(parents=True, exist_ok=True)
    call_command("backup_ledger", directory=str(backup_dir), verbosity=0)
    snapshots = sorted(
        backup_dir.glob("ledger-*"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not snapshots:
        raise RuntimeError("No verified database backup was created. Upgrade cancelled.")
    metadata = {
        "backup": str(snapshots[0]),
        "backend": connection.vendor,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (rollback / "checkpoint.json").write_text(json.dumps(metadata), encoding="utf8")
    LOG.info("Upgrade checkpoint created for %s", connection.vendor)


def post_install():
    _logger()
    _django()
    from django.core.management import call_command
    from django.db import connection

    root, rollback, _ = locations()
    backup = rollback / "checkpoint.json"
    if backup.is_file():
        stored = json.loads(backup.read_text(encoding="utf8"))
        if stored["backend"] != connection.vendor:
            raise RuntimeError("Database pin changed between installer versions")
    # Migrate the existing authoritative backend. Django migration errors
    # abort the upgrade, so Inno Setup can restore the prior installation.
    call_command("migrate", interactive=False, verbosity=0)
    call_command("check", verbosity=0)
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    marker = root / "update-required.json"
    marker.unlink(missing_ok=True)
    (rollback / "upgrade-succeeded").write_text("ok", encoding="ascii")
    LOG.info("Post-install migration and checks successful")


def restore_database():
    _logger()
    _django()
    root, rollback, _ = locations()
    record = json.loads((rollback / "checkpoint.json").read_text(encoding="utf8"))
    backup = Path(record["backup"])
    if not backup.is_relative_to(rollback.resolve()) or not backup.is_file():
        raise RuntimeError("Unsafe or missing database rollback snapshot")
    from django.core.management import call_command

    call_command(
        "restore_ledger", str(backup),
        apply=True, confirm="RESTORE-LEDGER", verbosity=0
    )
    LOG.warning("Restored pre-upgrade database after failed migration")


def run_action(action):
    try:
        if action == "--prepare-upgrade":
            prepare()
        elif action == "--post-upgrade-check":
            post_install()
        elif action == "--restore-upgrade":
            restore_database()
        else:
            raise ValueError("Unsupported desktop upgrade action")
        return 0
    except Exception:
        LOG.exception("Desktop upgrade action failed: %s", action)
        return 1
