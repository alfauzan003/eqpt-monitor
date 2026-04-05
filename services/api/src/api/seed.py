"""Seed equipment table from equipment.yaml."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import asyncpg
import yaml

logger = logging.getLogger(__name__)


def parse_equipment_yaml(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text())
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "type": item["type"],
            "location": item["location"],
            "metadata": item.get("metadata", {}),
        }
        for item in data["equipment"]
    ]


async def seed_equipment(pool: asyncpg.Pool, path: Path) -> int:
    rows = parse_equipment_yaml(path)
    async with pool.acquire() as conn:
        for row in rows:
            await conn.execute(
                """
                INSERT INTO equipment (id, name, type, location, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    location = EXCLUDED.location,
                    metadata = EXCLUDED.metadata;
                """,
                row["id"],
                row["name"],
                row["type"],
                row["location"],
                json.dumps(row["metadata"]),
            )
    logger.info("seeded %d equipment rows", len(rows))
    return len(rows)
