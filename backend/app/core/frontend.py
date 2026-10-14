"""Same-origin, built-only frontend. Never fall back from unknown API paths to HTML."""

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

UUID_PATH = r"[0-9a-f-]{36}"
PAGES = re.compile(
    rf"(?:/|/projects|/projects/new|/methodology|/projects/{UUID_PATH}/"
    rf"(?:overview|runs|trends|runs/new|setup/[a-z-]+)|/runs/{UUID_PATH}/"
    r"(?:overview|data|predictions|confidence|performance|calibration|errors|slices|report|"
    r"features/f[0-9]{3}))/?$"
)


def is_frontend_read(path: str, root: Path | None) -> bool:
    return root is not None and (bool(PAGES.fullmatch(path)) or path.startswith("/assets/"))


def mount_frontend(app: FastAPI, root: Path) -> None:
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if not PAGES.fullmatch("/" + path):
            raise HTTPException(404, "Page not found.")
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
