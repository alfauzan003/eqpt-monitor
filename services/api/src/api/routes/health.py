"""Health endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Response
from fastapi import status as http_status

from api.db import get_pool
from api.redis_client import get_client

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict:
    deps: dict[str, str] = {}
    all_ok = True

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        deps["timescaledb"] = "ok"
    except Exception:
        deps["timescaledb"] = "error"
        all_ok = False

    try:
        client = get_client()
        await client.ping()
        deps["redis"] = "ok"
    except Exception:
        deps["redis"] = "error"
        all_ok = False

    if not all_ok:
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "healthy" if all_ok else "degraded",
        "dependencies": deps,
        "version": "0.1.0",
    }
