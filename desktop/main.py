"""One-process Windows KC Ledger: Django, PostgreSQL/SQLite, Waitress, WebView2."""
import ctypes
import logging
import os
import secrets
import socket
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.request import urlopen

LOG = logging.getLogger("kc-ledger.desktop")


def root_data() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is missing.")
    root = Path(local) / "KCLedger"
    root.mkdir(parents=True, exist_ok=True)
    return root


def signing_key(root: Path) -> str:
    path = root / ".session-key"
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        if len(key) < 50:
            raise RuntimeError("Local session key is damaged.")
        return key
    key = secrets.token_urlsafe(64)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(key)
    return key


def first_owner(recover=False):
    from tkinter import Tk, Label, Entry, Button, messagebox
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    users = get_user_model()
    if not recover and users.objects.filter(is_staff=True, is_active=True).exists():
        return
    root = Tk()
    root.title("KC Ledger — Owner recovery" if recover else "KC Ledger — Owner setup")
    root.geometry("430x330")
    root.configure(bg="#F8F9FA")
    fields = {}
    for title, key, is_secret in (
        ("Owner username", "username", False),
        ("Password (minimum 16 characters)", "password", True),
        ("Confirm password", "confirm", True),
    ):
        Label(root, text=title, anchor="w", bg="#F8F9FA", fg="#0B1B3D").pack(
            fill="x", padx=24, pady=(14, 3)
        )
        entry = Entry(root, show="*" if is_secret else "")
        entry.pack(fill="x", padx=24, ipady=5)
        fields[key] = entry

    def create():
        username = fields["username"].get().strip()
        password = fields["password"].get()
        if not username or password != fields["confirm"].get():
            messagebox.showerror("Setup", "Enter a username and matching passwords.")
            return
        try:
            validate_password(password, user=users(username=username))
        except ValidationError as error:
            messagebox.showerror("Password", "\n".join(error.messages))
            return
        if recover:
            owner = users.objects.filter(username=username, is_superuser=True, is_active=True).first()
            if owner is None:
                messagebox.showerror("Recovery", "Enter the existing owner username.")
                return
            owner.set_password(password)
            owner.save(update_fields=["password"])
            messagebox.showinfo("Recovery", "Password changed. Sign in with the new password.")
            root.destroy()
            return
        if users.objects.filter(username=username).exists():
            messagebox.showerror("Setup", "Username already exists.")
            return
        users.objects.create_superuser(username=username, email="", password=password)
        root.destroy()

    Button(root, text="Reset owner password" if recover else "Create owner account", command=create).pack(pady=22)
    root.mainloop()
    if not users.objects.filter(is_staff=True, is_active=True).exists():
        raise RuntimeError("Owner setup was cancelled.")


def run():
    if os.name != "nt":
        raise RuntimeError("The native KC Ledger host requires Windows 10 or 11.")
    data = root_data()
    handler = RotatingFileHandler(
        data / "kc-ledger.log", maxBytes=2_000_000, backupCount=4, encoding="utf-8"
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    # If a verified post-update migration succeeded but the following launch
    # crashed before health, let the owner return to preserved old binaries.
    boot_marker = data / "post-update-boot.json"
    if boot_marker.is_file():
        import json
        from tkinter import Tk, messagebox

        state = json.loads(boot_marker.read_text(encoding="utf-8"))
        if state.get("state") == "starting":
            ui = Tk()
            ui.withdraw()
            rollback = data / "rollback" / "previous-program" / "KC Ledger.exe"
            recover = rollback.is_file() and messagebox.askyesno(
                "KC Ledger recovery",
                "An upgraded version did not finish starting. Restore the previous "
                "database snapshot and launch the preserved previous version?",
                parent=ui,
            )
            ui.destroy()
            if recover:
                from desktop.upgrade import restore_database
                import subprocess

                restore_database()
                boot_marker.unlink(missing_ok=True)
                subprocess.Popen([str(rollback)], close_fds=True)
                return
        else:
            boot_marker.write_text(json.dumps({"state": "starting"}), encoding="utf-8")
    # Allow the owner to configure local PostgreSQL without system-wide secrets.
    # This file is private per-user and is never bundled with the installer.
    from dotenv import load_dotenv

    load_dotenv(data / ".env", override=False)
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, r"Local\KCLedgerDesktop")
    if not mutex or kernel.GetLastError() == 183:
        raise RuntimeError("KC Ledger is already running or cannot acquire its lock.")
    server = None
    worker = None
    try:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        sys.path.insert(0, str(base))
        sys.path.insert(0, str(base / "backend"))
        os.environ.update({
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_SECRET_KEY": signing_key(data),
            "DJANGO_DEBUG": "0",
            "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
            "LEDGER_DB_PATH": str(data / "ledger.sqlite3"),
            "LEDGER_DB_PIN_PATH": str(data / ".database-backend"),
            "LEDGER_BACKUP_DIR": str(data / "backups"),
            "LEDGER_DESKTOP": "1",
            "COOKIE_SECURE": "0",
            "RUN_SCHEDULER": "0",
        })
        # Desktop auto-selects local PostgreSQL on first use, but never switches
        # a pinned financial database during outages or after recovery.
        os.environ.setdefault("LEDGER_DB_ENGINE", "auto")
        os.environ.setdefault("LEDGER_ALLOW_SQLITE_FALLBACK", "1")
        import django
        django.setup()
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from ledger.jobs import start_scheduler, stop_scheduler
        from waitress import create_server
        import webview

        from django.db import connection

        # Protect existing financial data before applying any schema upgrade.
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.django_migrations')")
                has_existing_schema = cursor.fetchone()[0] is not None
            if has_existing_schema:
                call_command("backup_ledger", verbosity=0)
        elif (data / "ledger.sqlite3").is_file():
            call_command("backup_ledger", verbosity=0)
        call_command("migrate", interactive=False, verbosity=0)
        first_owner()

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(64)
        port = listener.getsockname()[1]
        server = create_server(get_wsgi_application(), sockets=[listener], threads=4)
        worker = threading.Thread(target=server.run, daemon=True)
        worker.start()
        for _ in range(50):
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.8) as resp:
                    if resp.status == 200:
                        break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Local API did not pass the startup health check.")

        if boot_marker.is_file():
            boot_marker.unlink(missing_ok=True)
        start_scheduler()
        from desktop import updater
        import random

        def delayed_check():
            time.sleep(random.uniform(4, 15))
            updater.check_in_background()

        threading.Thread(target=delayed_check, daemon=True).start()
        webview.create_window(
            "KC Ledger", f"http://127.0.0.1:{port}/",
            width=1360, height=860, min_size=(960, 640),
            text_select=True,
        )
        webview.start(gui="edgechromium", debug=False)
    finally:
        try:
            from ledger.jobs import stop_scheduler
            stop_scheduler()
        except Exception:
            LOG.exception("Failed to stop scheduler")
        if server:
            server.close()
        if worker:
            worker.join(timeout=5)
        kernel.CloseHandle(ctypes.c_void_p(mutex))
        from desktop import updater

        command = data / "install-on-exit"
        if command.exists():
            command.unlink(missing_ok=True)
            try:
                updater.launch_pending()
            except Exception:
                LOG.exception("Failed to start the verified installer")




def self_test() -> None:
    """Exercise bundled backend, migrations, static HTML, financial API and PDF."""
    import json
    import tempfile
    from datetime import date, timedelta
    from decimal import Decimal

    report_path = os.environ.get("LEDGER_SMOKE_REPORT")
    result = {"status": "failed", "checks": []}
    try:
        temp = tempfile.TemporaryDirectory(prefix="kc-ledger-smoke-")
        try:
            folder = temp.name
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
            sys.path.insert(0, str(base))
            sys.path.insert(0, str(base / "backend"))
            os.environ.update({
                "DJANGO_SETTINGS_MODULE": "config.settings",
                "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
                "DJANGO_DEBUG": "0",
                "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
                "LEDGER_DB_ENGINE": "sqlite",
                "LEDGER_DB_PATH": str(Path(folder) / "smoke.sqlite3"),
                "LEDGER_DESKTOP": "1",
                "RUN_SCHEDULER": "0",
                "COOKIE_SECURE": "0",
            })
            import django

            django.setup()
            # Verify that the frozen Windows distribution can load PostgreSQL's
            # bundled libpq driver, even though the smoke DB is SQLite.
            from psycopg import pq

            assert pq.__impl__ == "binary", (
                f"Packaged PostgreSQL binary driver is unavailable: {pq.__impl__}"
            )
            result["checks"].append("PostgreSQL binary driver bundled")
            from django.contrib.auth import get_user_model
            from django.core.management import call_command
            from django.test import Client as TestClient
            from ledger.models import Client, Invoice, Payment

            call_command("migrate", interactive=False, verbosity=0)
            result["checks"].append("Migrations applied")
            user = get_user_model().objects.create_user(
                username="smoke-owner", password=secrets.token_urlsafe(36), is_staff=True
            )
            browser = TestClient()
            browser.force_login(user)
            health = browser.get("/api/health")
            assert health.status_code == 200, f"API health: {health.status_code}"
            result["checks"].append("API health 200")

            page = browser.get("/")
            assert page.status_code == 200, f"React shell: {page.status_code}"
            assert b"KC Ledger" in b"".join(page.streaming_content), "React HTML missing brand"
            result["checks"].append("Packaged React HTML served")

            customer = Client.objects.create(name="Desktop smoke test client")
            inv = Invoice.objects.create(
                client=customer, number="SMOKE-001", title="Desktop validation",
                amount=Decimal("100.00"), currency="USD",
                issue_date=date.today(), due_date=date.today() + timedelta(days=14),
                status=Invoice.Status.SENT,
            )
            payment = browser.post(
                "/api/payments",
                data=json.dumps({
                    "invoice_id": inv.pk, "amount": "25.00",
                    "paid_on": date.today().isoformat(), "method": "manual",
                    "reference": "DESKTOP-SMOKE-001",
                }),
                content_type="application/json",
            )
            assert payment.status_code == 200, (
                f"Payment API returned {payment.status_code}: {payment.content[:1000]!r}"
            )
            assert Payment.objects.filter(invoice=inv).count() == 1
            result["checks"].append("Financial payment transaction persisted")

            pdf = browser.get(f"/api/invoices/{inv.pk}/pdf")
            assert pdf.status_code == 200, f"Invoice PDF response {pdf.status_code}"
            assert pdf.content.startswith(b"%PDF"), "Invoice PDF invalid"
            result["checks"].append("Portable PDF generated")

            from django.db import connection
            connection.close()
            assert Invoice.objects.get(pk=inv.pk).number == "SMOKE-001"
            result["checks"].append("SQLite persistence after reconnect")
            result["status"] = "passed"
        finally:
            from django.db import connections
            connections.close_all()
            temp.cleanup()
    except Exception as exc:
        result["error"] = repr(exc)
        LOG.exception("Packaged desktop smoke test failed")
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    if result["status"] != "passed":
        raise RuntimeError("Desktop self-test failed: " + result.get("error", "unknown"))


def main():
    try:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        if str(base) not in sys.path:
            sys.path.insert(0, str(base))
        actions = {"--prepare-upgrade", "--post-upgrade-check", "--restore-upgrade"}
        selected = actions.intersection(sys.argv[1:])
        if selected:
            if len(selected) != 1:
                raise RuntimeError("Only one upgrade action is allowed")
            from desktop.upgrade import run_action

            sys.exit(run_action(next(iter(selected))))
        if "--recover-owner" in sys.argv:
            from desktop.upgrade import _django
            _django()
            first_owner(recover=True)
        elif "--self-test" in sys.argv:
            self_test()
        else:
            run()
    except Exception as exc:
        LOG.exception("KC Ledger desktop startup failed")
        if "--self-test" in sys.argv:
            sys.exit(1)
        try:
            from tkinter import Tk, messagebox
            root = Tk()
            root.withdraw()
            messagebox.showerror(
                "KC Ledger cannot start",
                str(exc) + "\n\nSee %LOCALAPPDATA%\\KCLedger\\kc-ledger.log.",
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
