"""Manifest URLs, rollout bucketing and version safety."""

import importlib.util
from pathlib import Path

import pytest

from desktop import updater


def test_version_prevents_downgrade_and_rejects_malformed():
    assert updater.version_tuple("1.4.12") > updater.version_tuple("1.4.2")
    with pytest.raises(ValueError):
        updater.version_tuple("1.4.0-evil")


def test_manifest_rejects_untrusted_installer_url():
    manifest = {
        "version": "1.2.3",
        "channel": "stable",
        "min_supported_version": "1.2.0",
        "installer_url": "https://evil.example/malware.exe",
        "sha256": "a" * 64,
        "rollout_percent": 100,
    }
    with pytest.raises(ValueError, match="pinned GitHub"):
        updater.validate_manifest(manifest)


def test_rollout_is_stable_for_one_installation(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert updater.eligible("1.2.3", 100)
    assert not updater.eligible("1.2.3", 0)
    assert updater.eligible("1.2.3", 30) == updater.eligible("1.2.3", 30)


def test_manifest_creates_sha_for_expected_signed_artifact(tmp_path):
    src = Path(__file__).resolve().parents[3] / "scripts" / "create_release_manifest.py"
    spec = importlib.util.spec_from_file_location("release_manifest_test", src)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    installer = tmp_path / "KCLedger-Setup-0.1.0.exe"
    installer.write_bytes(b"test-only-binary")
    result = module.make_manifest(installer, "0.1.0", "stable", "0.1.0", 100, "")
    assert result["sha256"]
    assert result["installer_url"].endswith("/v0.1.0/KCLedger-Setup-0.1.0.exe")
