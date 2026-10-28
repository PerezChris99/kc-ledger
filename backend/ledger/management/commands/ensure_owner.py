import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Create the initial staff superuser from environment secrets, if absent."

    def handle(self, *args, **options):
        username = os.environ.get("LEDGER_USERNAME", "").strip()
        password = os.environ.get("LEDGER_PASSWORD", "")
        secret = os.environ.get("DJANGO_SECRET_KEY", "")
        debug = os.environ.get("DJANGO_DEBUG", "0").lower() in {"1", "true", "yes"}
        if not username:
            raise CommandError("LEDGER_USERNAME must be configured.")
        if len(password) < 16 or password.startswith("replace-with-"):
            raise CommandError("Set LEDGER_PASSWORD to a unique password of at least 16 characters.")
        if not debug and (len(secret) < 40 or secret.startswith("unsafe-") or secret.startswith("replace-with-")):
            raise CommandError("Set DJANGO_SECRET_KEY to a random secret of at least 40 characters.")
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            User.objects.create_superuser(username=username, email="", password=password)
            self.stdout.write(self.style.SUCCESS(f"Created owner account {username}."))
        elif not user.is_staff or not user.is_active:
            raise CommandError("The configured owner account exists but is not an active staff account.")
        else:
            self.stdout.write("Owner account already exists; existing password was not changed.")
