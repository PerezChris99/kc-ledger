import os
import sys
from pathlib import Path
from django.apps import AppConfig

class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ledger"

    def ready(self):
        from django.db.backends.signals import connection_created
        from . import db
        connection_created.connect(db.configure_sqlite, dispatch_uid="ledger.configure_sqlite")
        command = Path(sys.argv[0]).name.lower() if sys.argv else ""
        if os.environ.get("RUN_SCHEDULER", "0") == "1" and command == "gunicorn":
            from .jobs import start_scheduler
            start_scheduler()
