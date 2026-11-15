"""One-process Windows KC Ledger: Django, SQLite, Waitress, WebView2."""
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


def first_owner():
    from tkinter import Tk, Label, Entry, Button, messagebox
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    users = get_user_model()
    if users.objects.filter(is_staff=True, is_active=True).exists():
        return
    root = Tk()
    root.title("KC Ledger — Owner setup")
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
        if users.objects.filter(username=username).exists():
            messagebox.showerror("Setup", "Username already exists.")
            return
        users.objects.create_superuser(username=username, email="", password=password)
        root.destroy()

    Button(root, text="Create owner account", command=create).pack(pady=22)
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
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None, False, r"Local\KCLedgerDesktop")
    if not mutex or kernel.GetLastError() == 183:
        raise RuntimeError("KC Ledger is already running or cannot acquire its lock.")
    server = None
    worker = None
    try:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        sys.path.insert(0, str(base / "backend"))
        os.environ.update({
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_SECRET_KEY": signing_key(data),
            "DJANGO_DEBUG": "0",
            "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
            "LEDGER_DB_PATH": str(data / "ledger.sqlite3"),
            "LEDGER_BACKUP_DIR": str(data / "backups"),
            "LEDGER_DESKTOP": "1",
            "COOKIE_SECURE": "0",
            "RUN_SCHEDULER": "0",
        })
        import django
        django.setup()
        from django.core.management import call_command
        from django.core.wsgi import get_wsgi_application
        from ledger.jobs import start_scheduler, stop_scheduler
        from waitress import create_server
        import webview

        if (data / "ledger.sqlite3").is_file():
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

        start_scheduler()
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


def main():
    try:
        run()
    except Exception as exc:
        LOG.exception("KC Ledger desktop startup failed")
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
