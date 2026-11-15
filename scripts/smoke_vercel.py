"""Verify the staged deployment before promotion."""

import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen


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
        with urlopen(Request(base + path, headers=headers), timeout=15) as response:
            if response.status != 200:
                raise RuntimeError("Staged API failed")
            obj = json.load(response)
        if path.endswith("/health") and obj.get("status") != "ok":
            raise RuntimeError("Staged API is unhealthy")
        if path.endswith("/version") and obj.get("git_sha") != os.environ["EXPECTED_SHA"][:12]:
            raise RuntimeError("Staged version does not match verified commit")
    print("Staged API health and version verified")


if __name__ == "__main__":
    main()
