"""Publish telemetry events + update hot cache."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import redis.asyncio as redis

from ingest.metrics import REDIS_PUBLISH_ERRORS

logger = logging.getLogger(__name__)

HOT_CACHE_TTL_SECONDS = 300


def build_publish_payload(
    *,
    equipment_id: str,
    time: datetime,
    status: str | None,
    batch_id: str | None,
    unit_id: str | None,
    metrics: dict[str, float],
) -> dict[str, Any]:
    return {
        "equipment_id": equipment_id,
        "time": time.isoformat(),
        "status": status,
        "batch_id": batch_id,
        "unit_id": unit_id,
        "metrics": metrics,
    }


def build_hot_cache_fields(
    *,
    status: str | None,
    batch_id: str | None,
    unit_id: str | None,
    unit_started_at: datetime | None,
    metrics: dict[str, float],
    updated_at: datetime,
) -> dict[str, str]:
    fields: dict[str, str] = {"updated_at": updated_at.isoformat()}
    if status is not None:
        fields["status"] = status
    if batch_id is not None:
        fields["current_batch_id"] = batch_id
    if unit_id is not None:
        fields["current_unit_id"] = unit_id
    if unit_started_at is not None:
        fields["unit_started_at"] = unit_started_at.isoformat()
    for name, value in metrics.items():
        fields[name] = str(value)
    return fields


class RedisPublisher:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def publish(self, equipment_id: str, payload: dict[str, Any]) -> None:
        channel = f"telemetry:{equipment_id}"
        try:
            await self._client.publish(channel, json.dumps(payload))
        except Exception:
            REDIS_PUBLISH_ERRORS.inc()
            logger.warning("redis publish failed for %s", equipment_id, exc_info=True)

    async def update_hot_cache(self, equipment_id: str, fields: dict[str, str]) -> None:
        key = f"equipment:latest:{equipment_id}"
        try:
            await self._client.hset(key, mapping=fields)
            await self._client.expire(key, HOT_CACHE_TTL_SECONDS)
        except Exception:
            REDIS_PUBLISH_ERRORS.inc()
            logger.warning("redis hot cache update failed for %s", equipment_id, exc_info=True)
