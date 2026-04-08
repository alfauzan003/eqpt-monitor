"""Telemetry history endpoint with auto resolution."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.db import get_pool
from api.query_router import Interval, select_interval, validate_range

router = APIRouter()


@router.get("/equipment/{equipment_id}/telemetry")
async def get_telemetry(
    equipment_id: str,
    frm: Annotated[datetime, Query(alias="from")],
    to: Annotated[datetime, Query()],
    metric: Annotated[list[str] | None, Query()] = None,
    interval: Annotated[str | None, Query()] = None,
) -> dict:
    try:
        validate_range(frm, to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "invalid_range", "detail": str(e)})

    if interval is None:
        resolved = select_interval(frm, to)
    else:
        try:
            resolved = Interval(interval)
        except ValueError:
            raise HTTPException(status_code=400, detail={"error": "invalid_interval"})

    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT 1 FROM equipment WHERE id = $1", equipment_id)
        if not exists:
            raise HTTPException(status_code=404, detail={"error": "not_found"})

        if resolved == Interval.RAW:
            rows = await _query_raw(conn, equipment_id, frm, to, metric)
            series = _group_raw(rows)
        else:
            table = "telemetry_1min" if resolved == Interval.MIN_1 else "telemetry_1hour"
            rows = await _query_agg(conn, table, equipment_id, frm, to, metric)
            series = _group_agg(rows)

    return {
        "equipment_id": equipment_id,
        "interval": resolved.value,
        "series": series,
    }


async def _query_raw(conn, equipment_id, frm, to, metric):
    sql = (
        "SELECT time, metric_name, value FROM telemetry "
        "WHERE equipment_id = $1 AND time >= $2 AND time < $3"
    )
    params = [equipment_id, frm, to]
    if metric:
        sql += " AND metric_name = ANY($4)"
        params.append(metric)
    sql += " ORDER BY time"
    return await conn.fetch(sql, *params)


async def _query_agg(conn, table, equipment_id, frm, to, metric):
    sql = (
        f"SELECT bucket, metric_name, avg_value, min_value, max_value FROM {table} "
        "WHERE equipment_id = $1 AND bucket >= $2 AND bucket < $3"
    )
    params = [equipment_id, frm, to]
    if metric:
        sql += " AND metric_name = ANY($4)"
        params.append(metric)
    sql += " ORDER BY bucket"
    return await conn.fetch(sql, *params)


def _group_raw(rows):
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["metric_name"], []).append(
            {"time": r["time"].isoformat(), "value": r["value"]}
        )
    return [{"metric": k, "points": v} for k, v in out.items()]


def _group_agg(rows):
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["metric_name"], []).append(
            {
                "time": r["bucket"].isoformat(),
                "avg": r["avg_value"],
                "min": r["min_value"],
                "max": r["max_value"],
            }
        )
    return [{"metric": k, "points": v} for k, v in out.items()]
