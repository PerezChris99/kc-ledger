"""Authenticated, publisher-pinned Windows updates for a single KC Ledger installation."""

import hashlib
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOG = logging.getLogger("kc-ledger.updater")

def _log_steps():
    from logging.handlers import RotatingFileHandler

    logger_root = base_dir() / "logs"
    logger_root.mkdir(parents=True, exist_ok=True)
    if not any(isinstance(h, RotatingFileHandler) for h in LOG.handlers):
        handler = RotatingFileHandler(
            logger_root / "update.log", maxBytes=2_000_000, backupCount=4,
            encoding="utf-8",
        )
        LOG.addHandler(handler)
        LOG.setLevel(logging.INFO)

REPO = "PerezChris99/kc-ledger"
MANIFEST_URL = f"https://github.com/{REPO}/releases/latest/download/latest.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
MAX_MANIFEST = 16384
MAX_INSTALLER = 350 * 1024 * 1024
_state_lock = threading.Lock()
_pending = None


def base_dir():
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is not configured")
    root = Path(local) / "KCLedger"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _cfg():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    path = root / "desktop" / "update_config.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def version_tuple(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError("Invalid semantic version")
    return tuple(int(x) for x in value.split("."))


def settings():
    path = base_dir() / "update-settings.json"
    if not path.exists():
        return {"policy": "auto_download", "channel": "stable"}
    obj = json.loads(path.read_text(encoding="utf-8"))
    return {
        "policy": obj["policy"] if obj.get("policy") in {
            "manual", "auto_download", "install_on_exit"
        } else "auto_download",
        "channel": obj["channel"] if obj.get("channel") in {"stable", "beta"} else "stable",
    }


def save_settings(policy, channel):
    if policy not in {"manual", "auto_download", "install_on_exit"}:
        raise ValueError("Unsupported update policy")
    if channel not in {"stable", "beta"}:
        raise ValueError("Unsupported update channel")
    root = base_dir()
    temp = root / "update-settings.json.tmp"
    temp.write_text(json.dumps({"policy": policy, "channel": channel}), encoding="utf-8")
    os.replace(temp, root / "update-settings.json")


def _https_json(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise RuntimeError("Update metadata must be fetched over HTTPS")
    with urlopen(Request(url, headers={"User-Agent": "KCLedger-Updater"}), timeout=12) as res:
        if urlparse(res.url).scheme != "https":
            raise RuntimeError("Manifest redirected outside HTTPS")
        data = res.read(MAX_MANIFEST + 1)
    if len(data) > MAX_MANIFEST:
        raise RuntimeError("Update manifest exceeds size limit")
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise ValueError("Invalid update manifest")
    return obj


def _installer_url(version):
    return (
        f"https://github.com/{REPO}/releases/download/v{version}/"
        f"KCLedger-Setup-{version}.exe"
    )


def validate_manifest(obj):
    version = obj.get("version")
    version_tuple(version)
    version_tuple(obj.get("min_supported_version"))
    if obj.get("channel") not in {"stable", "beta"}:
        raise ValueError("Invalid release channel")
    if obj.get("installer_url") != _installer_url(version):
        raise ValueError("Installer URL does not match the pinned GitHub release")
    if not re.fullmatch("[0-9a-fA-F]{64}", str(obj.get("sha256", ""))):
        raise ValueError("Missing SHA-256 fingerprint")
    rollout = obj.get("rollout_percent")
    if isinstance(rollout, bool) or not isinstance(rollout, int) or rollout < 0 or rollout > 100:
        raise ValueError("Invalid rollout percentage")
    if len(str(obj.get("release_notes", ""))) > 4000:
        raise ValueError("Release notes exceed limit")
    return obj


def _install_id():
    path = base_dir() / ".update-install-id"
    if not path.exists():
        try:
            with path.open("x", encoding="ascii") as handle:
                handle.write(secrets.token_hex(24))
        except FileExistsError:
            pass
    return path.read_text(encoding="ascii").strip()


def eligible(version, percent):
    digest = hashlib.sha256((_install_id() + ":" + version).encode()).digest()
    return int.from_bytes(digest[:8], "big") % 100 < percent


def _signature_details(path):
    # Do not trust manifest-provided publisher fingerprints. The allowed
    # certificate thumbprint is embedded at signed build time.
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    script = root / "desktop" / "verify_signature.ps1"
    proc = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(script), str(path),
        ],
        check=False, capture_output=True, text=True, timeout=25,
    )
    if proc.returncode:
        raise RuntimeError("Windows Authenticode validation failed")
    return json.loads(proc.stdout)


def verify_installer(path, manifest):
    cfg = _cfg()
    publisher = str(cfg.get("publisher_thumbprint", "")).upper().replace(" ", "")
    if not re.fullmatch("[0-9A-F]{40,64}", publisher):
        raise RuntimeError("No trusted release publisher configured in this desktop build")
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    if not secrets.compare_digest(digest.hexdigest(), manifest["sha256"].lower()):
        raise RuntimeError("Downloaded installer SHA-256 mismatch")
    signature = _signature_details(path)
    if signature.get("Status") != "Valid":
        raise RuntimeError("Downloaded installer is unsigned or its signature is invalid")
    actual = str(signature.get("Thumbprint") or "").upper().replace(" ", "")
    if not secrets.compare_digest(actual, publisher):
        raise RuntimeError("Downloaded installer publisher does not match pinned certificate")
    expected = manifest["version"]
    file_version = str(signature.get("FileVersion") or "")
    if not (file_version == expected or file_version.startswith(expected + ".")):
        raise RuntimeError("Installer embedded version does not match its manifest")


def _download_verified(manifest):
    root = base_dir() / "updates"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"KCLedger-Setup-{manifest['version']}.exe"
    if destination.exists():
        try:
            verify_installer(destination, manifest)
            return destination
        except (ValueError, RuntimeError):
            destination.unlink()
    fd, staged = tempfile.mkstemp(prefix=".kc-update-", suffix=".exe", dir=root)
    os.close(fd)
    path = Path(staged)
    try:
        with urlopen(
            Request(manifest["installer_url"], headers={"User-Agent": "KCLedger-Updater"}),
            timeout=30,
        ) as response, path.open("wb") as file:
            host = urlparse(response.url)
            if host.scheme != "https" or not (
                host.hostname == "github.com"
                or host.hostname == "release-assets.githubusercontent.com"
            ):
                raise RuntimeError("Installer redirect is not on a trusted GitHub host")
            size = 0
            while chunk := response.read(256 * 1024):
                size += len(chunk)
                if size > MAX_INSTALLER:
                    raise RuntimeError("Installer is unexpectedly large")
                file.write(chunk)
        verify_installer(path, manifest)
        os.replace(path, destination)
        return destination
    finally:
        path.unlink(missing_ok=True)


def check(manual=False):
    """Return safe update metadata; never execute an unverified binary."""
    from config.version import build_info

    _log_steps()
    current = build_info()
    config = settings()
    LOG.info("Checking %s desktop update channel", config["channel"])
    cfg = _cfg()
    source = cfg.get("beta_manifest_url") if config["channel"] == "beta" else cfg.get("manifest_url")
    manifest = validate_manifest(_https_json(source or MANIFEST_URL))
    required = version_tuple(current["version"]) < version_tuple(manifest["min_supported_version"])
    if manifest["channel"] != config["channel"] and not required:
        return {"status": "no_update", "version": current["version"]}
    if version_tuple(manifest["version"]) <= version_tuple(current["version"]):
        return {"status": "no_update", "version": current["version"]}
    if not required and not eligible(manifest["version"], manifest["rollout_percent"]):
        return {"status": "staged", "version": current["version"]}
    if not _cfg().get("publisher_thumbprint"):
        return {"status": "untrusted_build", "message": "Trusted publisher not configured"}
    if config["policy"] == "manual" and not manual and not required:
        return {"status": "available", "version": manifest["version"]}
    path = _download_verified(manifest)
    LOG.info("Verified signed installer for version %s", manifest["version"])
    global _pending
    with _state_lock:
        _pending = str(path)
    if required:
        (base_dir() / "update-required.json").write_text(
            json.dumps({"min_supported_version": manifest["min_supported_version"]}),
            encoding="utf-8",
        )
    return {
        "status": "ready", "version": manifest["version"],
        "required": required, "release_notes": manifest.get("release_notes", ""),
    }


def pending_installer():
    with _state_lock:
        path = _pending
    return Path(path) if path else None


def launch_pending():
    path = pending_installer()
    if path is None or not path.is_file():
        return False
    # Always check again immediately before executing a staged file.
    manifest = validate_manifest(_https_json(_cfg().get("manifest_url") or MANIFEST_URL))
    if path.name != f"KCLedger-Setup-{manifest['version']}.exe":
        return False
    verify_installer(path, manifest)
    LOG.info("Starting signed KC Ledger installer: %s", path.name)
    subprocess.Popen(
        [str(path), "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
        close_fds=True,
    )
    return True


def check_in_background():
    def task():
        try:
            status = check()
            if status.get("status") == "ready":
                from tkinter import Tk, messagebox

                ui = Tk()
                ui.withdraw()
                title = f"KC Ledger v{status['version']}"
                notice = "A mandatory security update is required." if status["required"] else "An update is ready. Restart and install now?"
                if messagebox.askyesno(title, notice, parent=ui):
                    # Defer installer execution until Waitress, SQLite and the
                    # WebView have shut down; caller owns that shutdown.
                    (base_dir() / "install-on-exit").write_text("1", encoding="ascii")
                    import webview

                    for window in webview.windows:
                        window.destroy()
                ui.destroy()
        except Exception:
            LOG.exception("Could not verify an update. Application data was not changed.")

    worker = threading.Thread(target=task, daemon=True, name="kc-ledger-updater")
    worker.start()
    return worker
