"""Public, read-only mirror of the current GitHub signed release manifest."""

import json
import logging
from urllib.request import Request, urlopen

from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)
API_URL = "https://api.github.com/repos/PerezChris99/kc-ledger/releases?per_page=15"


@require_GET
def latest(request, channel="stable"):
    if channel not in ("stable", "beta"):
        return JsonResponse({"detail": "Not found"}, status=404)
    try:
        with urlopen(
            Request(
                API_URL,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "KCLedger"},
            ),
            timeout=6,
        ) as response:
            releases = json.loads(response.read(128_000))
        for release in releases:
            if release.get("draft") or bool(release.get("prerelease")) != (channel == "beta"):
                continue
            manifest = next(
                (a for a in release.get("assets", []) if a.get("name") == "latest.json"),
                None,
            )
            if not manifest:
                continue
            url = manifest.get("browser_download_url", "")
            if not url.startswith(
                "https://github.com/PerezChris99/kc-ledger/releases/download/"
            ):
                continue
            with urlopen(Request(url, headers={"User-Agent": "KCLedger"}), timeout=8) as body:
                payload = body.read(16385)
            if len(payload) > 16384:
                break
            obj = json.loads(payload)
            if obj.get("channel") != channel or obj.get("version") != release["tag_name"].removeprefix("v"):
                break
            reply = JsonResponse(obj)
            reply["Cache-Control"] = "public, max-age=120"
            return reply
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("GitHub update manifest unavailable", exc_info=True)
    return JsonResponse({"detail": "No verified release manifest available"}, status=503)
