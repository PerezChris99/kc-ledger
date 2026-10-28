from django.apps import AppConfig

class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ledger"

    def ready(self):
        from django.db.backends.signals import connection_created
        from . import db  # noqa: F401
        connection_created.connect(db.configure_sqlite, dispatch_uid="ledger.configure_sqlite")
