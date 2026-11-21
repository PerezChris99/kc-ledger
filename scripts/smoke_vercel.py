"""Check staged Vercel Django API *and* installable PWA before promotion.

Fail closed if a rewrite serves index.html instead of a PNG, manifest or SW.
The same authenticated staged URL is used for API checks.
"""

import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PNG_HEADER = bytes.fromhex("89504e470d0a1a0a")


def _read(base, path, headers):
    with urlopen(Request(base + path, headers=headers), timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("Staged endpoint failed: " + path)
        content_type = response.headers.get("Content-Type", "").lower()
        cache_control = response.headers.get("Cache-Control", "").lower()
        data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise RuntimeError("Staged endpoint unexpectedly large: " + path)
        return content_type, cache_control, data


def main():
    base = os.environ["DEPLOYMENT_URL"].rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".vercel.app"):
        raise RuntimeError("Invalid staged Vercel deployment URL")
    headers = {}
    bypass = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET")
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    for path in ("/api/health", "/api/version"):
        mime, cache, body = _read(base, path, headers)
        if "json" not in mime or "no-store" not in cache:
            raise RuntimeError("Staged API does not use non-cacheable JSON: " + path)
        obj = json.loads(body)
        if path.endswith("/health") and obj.get("status") != "ok":
            raise RuntimeError("Staged API is unhealthy")
        if path.endswith("/version") and obj.get("git_sha") != os.environ["EXPECTED_SHA"][:12]:
            raise RuntimeError("Staged version does not match verified commit")

    html_mime, _, html = _read(base, "/", headers)
    if "html" not in html_mime or b"manifest.webmanifest" not in html:
        raise RuntimeError("PWA application entry point or linked manifest missing")
    manifest_mime, _, data = _read(base, "/manifest.webmanifest", headers)
    if "json" not in manifest_mime:
        raise RuntimeError("PWA manifest request was incorrectly rewritten")
    manifest = json.loads(data)
    if (
        manifest.get("name") != "KC Ledger \u2014 Financial Operations"
        or manifest.get("display") != "standalone"
        or manifest.get("scope") != "/"
    ):
        raise RuntimeError("PWA manifest is invalid")
    png_icons = {
        (x.get("src"), x.get("sizes"), x.get("purpose"))
        for x in manifest.get("icons", [])
    }
    for name, size, purpose in (
        ("/pwa/icon-192.png", 192, "any"),
        ("/pwa/icon-512.png", 512, "any"),
        ("/pwa/maskable-512.png", 512, "maskable"),
    ):
        if (name, f"{size}x{size}", purpose) not in png_icons:
            raise RuntimeError("Missing install icon: " + name)
        mime, _, payload = _read(base, name, headers)
        if not mime.startswith("image/png") or not payload.startswith(PNG_HEADER):
            raise RuntimeError("PWA icon routed to HTML or an invalid file: " + name)
        if int.from_bytes(payload[16:20], "big") != size:
            raise RuntimeError("PWA icon dimensions do not match manifest: " + name)
    sw_type, sw_cache, worker = _read(base, "/sw.js", headers)
    if "javascript" not in sw_type or "no-cache" not in sw_cache:
        raise RuntimeError("Service worker is not an uncached JavaScript response")
    if b"precacheAndRoute" not in worker:
        raise RuntimeError("Service worker does not contain an offline shell")
    print("Staged Django API, revision SHA, PWA manifest, icons and service worker verified")


if __name__ == "__main__":
    main()
