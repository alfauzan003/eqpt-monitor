"""Ingest service entry point."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis

from ingest.batch_buffer import BatchBuffer, Sample
from ingest.config import settings
from ingest.db_writer import DbWriter
from ingest.logging_config import setup_logging
from ingest.metrics import (
    INGEST_MESSAGES_TOTAL,
    OPCUA_CONNECTION_ATTEMPTS,
    OPCUA_SUBSCRIPTION_ACTIVE,
)
from ingest.opcua_client import EquipmentState, connect_and_subscribe
from prometheus_client import start_http_server
from ingest.redis_publisher import (
    RedisPublisher,
    build_hot_cache_fields,
    build_publish_payload,
)

setup_logging()
logger = logging.getLogger("ingest")


async def _connect_db_with_retry() -> asyncpg.Pool:
    delay = 1.0
    while True:
        try:
            return await asyncpg.create_pool(
                dsn=settings.postgres_dsn, min_size=1, max_size=5
            )
        except Exception:
            logger.warning("postgres connect failed, retrying in %.1fs", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


async def _connect_opcua_with_retry(on_update, state_store):
    delay = 1.0
    while True:
        try:
            result = await connect_and_subscribe(
                settings.opcua_endpoint, on_update, state_store
            )
            OPCUA_CONNECTION_ATTEMPTS.labels(result="success").inc()
            OPCUA_SUBSCRIPTION_ACTIVE.set(1)
            return result
        except Exception:
            OPCUA_CONNECTION_ATTEMPTS.labels(result="failure").inc()
            logger.warning("opcua connect failed, retrying in %.1fs", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60.0)


async def run() -> None:
    start_http_server(9090)
    logger.info("prometheus metrics server started on :9090")
    pool = await _connect_db_with_retry()
    db_writer = DbWriter(pool)

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    publisher = RedisPublisher(redis_client)

    buffer = BatchBuffer(
        max_size=settings.batch_max_size,
        max_age_seconds=settings.batch_max_age_seconds,
        overflow_limit=settings.batch_overflow_limit,
    )

    last_unit: dict[str, tuple[str | None, datetime]] = {}

    def on_update(equipment_id: str, st: EquipmentState, now: datetime) -> None:
        if st.metrics is None:
            return
        for metric_name in st.metrics:
            INGEST_MESSAGES_TOTAL.labels(
                equipment_id=equipment_id, metric_name=metric_name
            ).inc()
        prev = last_unit.get(equipment_id)
        if prev is None or prev[0] != st.unit_id:
            last_unit[equipment_id] = (st.unit_id, now)
        unit_started_at = last_unit[equipment_id][1]

        for metric_name, value in st.metrics.items():
            buffer.add(
                Sample(
                    time=now,
                    equipment_id=equipment_id,
                    metric_name=metric_name,
                    value=value,
                    status=st.status,
                    batch_id=st.batch_id,
                    unit_id=st.unit_id,
                )
            )

        payload = build_publish_payload(
            equipment_id=equipment_id,
            time=now,
            status=st.status,
            batch_id=st.batch_id,
            unit_id=st.unit_id,
            metrics=dict(st.metrics),
        )
        fields = build_hot_cache_fields(
            status=st.status,
            batch_id=st.batch_id,
            unit_id=st.unit_id,
            unit_started_at=unit_started_at,
            metrics=dict(st.metrics),
            updated_at=now,
        )
        asyncio.create_task(publisher.publish(equipment_id, payload))
        asyncio.create_task(publisher.update_hot_cache(equipment_id, fields))

    state_store: dict[str, EquipmentState] = {}
    opcua_client = await _connect_opcua_with_retry(on_update, state_store)

    try:
        while True:
            now = datetime.now(timezone.utc)
            if buffer.should_flush(now):
                batch = buffer.drain()
                try:
                    await db_writer.write_batch(batch)
                except Exception:
                    logger.exception("db write failed for batch of %d", len(batch))
            await asyncio.sleep(0.2)
    finally:
        await opcua_client.disconnect()
        await pool.close()
        await redis_client.aclose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
