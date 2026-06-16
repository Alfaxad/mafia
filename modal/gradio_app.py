from __future__ import annotations

from pathlib import Path

import modal


APP_NAME = "ai-native-mafia-gradio"
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FRONTEND_DIST = ROOT / "frontend" / "dist"
FRONTEND_ASSETS = ROOT / "frontend" / "public" / "assets"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("gradio[mcp]==6.18.0", "pydantic>=2.8", "modal>=1.3")
    .add_local_dir(str(SRC), "/root/src")
    .add_local_dir(str(FRONTEND_DIST), "/root/frontend/dist")
    .add_local_dir(str(FRONTEND_ASSETS), "/root/frontend/public/assets")
)

app = modal.App(APP_NAME)


@app.function(image=image, timeout=60 * 20, scaledown_window=60 * 10, max_containers=1)
@modal.asgi_app()
def web():
    import os
    import sys

    os.environ.setdefault("MAFIA_SESSION_BACKEND", "modal")
    os.environ.setdefault("MAFIA_SESSION_DICT", "ai-native-mafia-sessions")
    sys.path.insert(0, "/root/src")
    from mafia.server.app import app as server_app

    return server_app
