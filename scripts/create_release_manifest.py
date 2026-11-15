"""Generate the public, hash-pinned manifest for a SIGNED Windows installer."""

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = "PerezChris99/kc-ledger"


def make_manifest(path, version, channel, minimum, rollout, notes):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release version must follow MAJOR.MINOR.PATCH")
    if not re.fullmatch(r"\d+\.\d+\.\d+", minimum):
        raise ValueError("Minimum version must be a semantic version")
    if channel not in {"stable", "beta"} or not 0 <= rollout <= 100:
        raise ValueError("Invalid channel or rollout")
    if path.name != f"KCLedger-Setup-{version}.exe" or not path.is_file():
        raise ValueError("Signed installer is missing or named incorrectly")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "version": version,
        "channel": channel,
        "min_supported_version": minimum,
        "installer_url": (
            f"https://github.com/{REPOSITORY}/releases/download/v{version}/"
            f"KCLedger-Setup-{version}.exe"
        ),
        "sha256": digest,
        "signature": "authenticode-sha256",
        "release_notes": notes[:4000],
        "published_at": datetime.now(timezone.utc).isoformat(),
        "rollout_percent": rollout,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("installer", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--channel", choices=["stable", "beta"], default="stable")
    parser.add_argument("--minimum", required=True)
    parser.add_argument("--rollout", type=int, default=100)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    canonical = Path("VERSION").read_text(encoding="utf8").strip()
    if args.version != canonical:
        raise SystemExit("Release tag does not match canonical VERSION")
    obj = make_manifest(
        args.installer, args.version, args.channel, args.minimum, args.rollout, args.notes
    )
    output = args.installer.parent
    (output / "latest.json").write_text(json.dumps(obj, indent=2) + "\n", encoding="utf8")
    (output / (args.installer.name + ".sha256")).write_text(
        obj["sha256"] + "  " + args.installer.name + "\n", encoding="ascii"
    )


if __name__ == "__main__":
    main()
