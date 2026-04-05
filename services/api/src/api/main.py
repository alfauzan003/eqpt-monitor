"""FastAPI app entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from api.config import settings
from api.db import close_pool, get_pool
from api.redis_client import close_client
from api.routes.health import router as health_router
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
        await seed_equipment(pool, Path(settings.equipment_config_path))
    except FileNotFoundError:
        logger.warning("equipment config not found at %s; skipping seed", settings.equipment_config_path)
    yield
    await close_pool()
    await close_client()


app = FastAPI(title="Factory Pulse API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router, prefix="/api")
