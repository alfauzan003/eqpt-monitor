"""Equipment list + detail endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.db import get_pool
from api.redis_client import get_client

router = APIRouter()

_META_METRIC_FIELDS = {
    "status",
    "current_batch_id",
    "current_unit_id",
    "unit_started_at",
    "updated_at",
}


def _split_latest(h: dict[str, str]) -> tuple[dict[str, object], dict[str, float]]:
    meta: dict[str, object] = {
        "status": h.get("status"),
        "current_batch_id": h.get("current_batch_id"),
        "current_unit_id": h.get("current_unit_id"),
        "unit_started_at": h.get("unit_started_at"),
        "updated_at": h.get("updated_at"),
    }
    metrics: dict[str, float] = {}
    for k, v in h.items():
        if k in _META_METRIC_FIELDS:
            continue
        try:
            metrics[k] = float(v)
        except (TypeError, ValueError):
            continue
    return meta, metrics


@router.get("/equipment")
async def list_equipment() -> dict:
    pool = await get_pool()
    client = get_client()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, type, location FROM equipment ORDER BY id"
        )

    result = []
    for row in rows:
        try:
            h = await client.hgetall(f"equipment:latest:{row['id']}")
        except Exception:
            h = {}
        meta, metrics = _split_latest(h) if h else ({}, {})
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "location": row["location"],
                "status": meta.get("status"),
                "current_batch_id": meta.get("current_batch_id"),
                "current_unit_id": meta.get("current_unit_id"),
                "unit_started_at": meta.get("unit_started_at"),
                "latest_metrics": metrics,
                "updated_at": meta.get("updated_at"),
            }
        )
    return {"equipment": result}


@router.get("/equipment/{equipment_id}")
async def get_equipment(equipment_id: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, type, location, metadata FROM equipment WHERE id = $1",
            equipment_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["type"],
        "location": row["location"],
        "metadata": row["metadata"],
    }


@router.get("/equipment/{equipment_id}/current")
async def get_equipment_current(equipment_id: str) -> dict:
    client = get_client()
    try:
        h = await client.hgetall(f"equipment:latest:{equipment_id}")
    except Exception:
        h = {}
    if not h:
        raise HTTPException(status_code=404, detail={"error": "no_current_data"})
    return {
        "equipment_id": equipment_id,
        "status": h.get("status"),
        "batch_id": h.get("current_batch_id"),
        "unit_id": h.get("current_unit_id"),
        "unit_started_at": h.get("unit_started_at"),
    }
