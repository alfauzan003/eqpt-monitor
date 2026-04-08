"""Batch traceability endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.db import get_pool

router = APIRouter()


@router.get("/batches/{batch_id}/telemetry")
async def get_batch_timeline(batch_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                equipment_id,
                MIN(time) AS started_at,
                MAX(time) AS ended_at,
                ARRAY_AGG(DISTINCT unit_id) AS units
            FROM telemetry
            WHERE batch_id = $1
            GROUP BY equipment_id
            ORDER BY started_at
            """,
            batch_id,
        )
    if not rows:
        raise HTTPException(status_code=404, detail={"error": "batch_not_found"})
    return {
        "batch_id": batch_id,
        "equipment_timeline": [
            {
                "equipment_id": r["equipment_id"],
                "started_at": r["started_at"].isoformat(),
                "ended_at": r["ended_at"].isoformat(),
                "units_processed": [u for u in r["units"] if u is not None],
            }
            for r in rows
        ],
    }
