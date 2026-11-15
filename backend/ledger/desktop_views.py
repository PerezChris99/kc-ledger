"""Desktop-only static React frontend served from the Windows loopback API."""

import mimetypes
import os
import sys
from pathlib import Path

from django.http import FileResponse, Http404


def serve_frontend(request, path=""):
    if os.environ.get("LEDGER_DESKTOP") != "1":
        raise Http404
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS) / "dist"
    else:
        root = Path(__file__).resolve().parents[2] / "dist"
    root = root.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise Http404("Invalid asset path.")
    if not target.is_file():
        if path.startswith("assets/") or Path(path).suffix:
            raise Http404("Asset is unavailable.")
        target = root / "index.html"
    if not target.is_file():
        raise Http404("Packaged frontend missing.")
    mime, _ = mimetypes.guess_type(str(target))
    response = FileResponse(target.open("rb"), content_type=mime or "application/octet-stream")
    response["Cache-Control"] = (
        "no-store"
        if target.name == "index.html"
        else "public, max-age=31536000, immutable"
        if path.startswith("assets/")
        else "no-cache"
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    return response
