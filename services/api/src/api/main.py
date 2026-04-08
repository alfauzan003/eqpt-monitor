"""FastAPI app entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path as _P

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.config import settings
from api.db import close_pool, get_pool
from api.redis_client import close_client
from api.routes.batches import router as batches_router
from api.routes.equipment import router as equipment_router
from api.routes.health import router as health_router
from api.routes.telemetry import router as telemetry_router
from api.websocket import router as ws_router
from api.seed import seed_equipment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    try:
        await seed_equipment(pool, _P(settings.equipment_config_path))
    except FileNotFoundError:
        logger.warning("equipment config not found at %s; skipping seed", settings.equipment_config_path)
    yield
    await close_pool()
    await close_client()


app = FastAPI(title="Factory Pulse API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
app.include_router(equipment_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(batches_router, prefix="/api")
app.include_router(ws_router)  # no /api prefix for ws

_static_dir = _P("/app/static")
if _static_dir.exists():
    # Serve hashed assets (JS/CSS bundles) from /assets
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    # All non-API paths return index.html (SPA client-side routing)
    @app.get("/", include_in_schema=False)
    async def spa_root() -> FileResponse:
        return FileResponse(_static_dir / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request) -> FileResponse:
        return FileResponse(_static_dir / "index.html")
