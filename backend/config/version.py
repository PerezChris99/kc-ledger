"""Public, secret-free build identity sourced only from the root VERSION file."""

import json
import os
import re
import sys
from pathlib import Path


def build_info():
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
        candidate = root / "backend" / "config" / "build_info.json"
        version_file = root / "VERSION"
    else:
        root = Path(__file__).resolve().parents[2]
        candidate = Path(__file__).resolve().with_name("build_info.json")
        version_file = root / "VERSION"

    version = version_file.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise RuntimeError("Invalid canonical KC Ledger VERSION file")
    info = json.loads(candidate.read_text(encoding="utf-8")) if candidate.exists() else {}
    # Environment metadata is nonsecret: Vercel can provide commit sha at runtime.
    sha = os.environ.get("VERCEL_GIT_COMMIT_SHA", os.environ.get("GITHUB_SHA", "unknown"))
    channel = info.get("channel", os.environ.get("LEDGER_RELEASE_CHANNEL", "stable"))
    minimum = info.get(
        "min_supported_version", os.environ.get("LEDGER_MIN_SUPPORTED_VERSION", "0.0.0")
    )
    if channel not in {"stable", "beta"}:
        raise RuntimeError("Invalid KC Ledger release channel")
    if not re.fullmatch(r"\d+\.\d+\.\d+", minimum):
        raise RuntimeError("Invalid minimum supported version")
    return {
        "version": version,
        "git_sha": info.get("git_sha", sha[:12] if sha != "unknown" else "unknown"),
        "build_time": info.get("build_time", os.environ.get("LEDGER_BUILD_TIME", "unknown")),
        "channel": channel,
        "min_supported_version": minimum,
    }
