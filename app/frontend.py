import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

logger = logging.getLogger(__name__)


def mount_frontend(app: FastAPI, dist_dir: str) -> None:
    """Serve the built SPA. Unknown non-API paths fall back to index.html
    so client-side routing works. Must be called after API routers."""
    dist = Path(dist_dir).resolve()
    index = dist / "index.html"
    if not index.is_file():
        logger.info("Frontend build not found at %s; skipping", dist)
        return

    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    api_prefix = settings.api_v1_prefix.strip("/").split("/")[0]

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        if full_path.split("/")[0] == api_prefix:
            raise HTTPException(status_code=404)
        file = (dist / full_path).resolve()
        if full_path and file.is_file() and file.is_relative_to(dist):
            return FileResponse(file)
        return FileResponse(index)
