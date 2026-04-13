"""Write batches to TimescaleDB."""
from __future__ import annotations

import logging
import time

import asyncpg

from ingest.batch_buffer import Sample
from ingest.metrics import INGEST_BATCH_LATENCY, INGEST_BATCH_SIZE, INGEST_DB_WRITE_ERRORS

logger = logging.getLogger(__name__)


class DbWriter:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write_batch(self, samples: list[Sample]) -> None:
        if not samples:
            return
        INGEST_BATCH_SIZE.observe(len(samples))
        rows = [
            (s.time, s.equipment_id, s.metric_name, s.value, s.status, s.batch_id, s.unit_id)
            for s in samples
        ]
        start = time.monotonic()
        try:
            async with self._pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO telemetry (time, equipment_id, metric_name, value, status, batch_id, unit_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (time, equipment_id, metric_name) DO NOTHING
                    """,
                    rows,
                )
            INGEST_BATCH_LATENCY.observe(time.monotonic() - start)
        except Exception:
            INGEST_DB_WRITE_ERRORS.inc()
            raise
