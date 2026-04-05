"""Load equipment configuration from YAML."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class EquipmentConfig(BaseModel):
    id: str
    name: str
    type: str
    location: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    metrics: list[str]
    unit_duration_seconds: int
    unit_id_prefix: str
    line: str = ""


def load_equipment_config(path: Path) -> list[EquipmentConfig]:
    if not path.exists():
        raise FileNotFoundError(f"equipment config not found: {path}")
    data = yaml.safe_load(path.read_text())
    return [EquipmentConfig(**item) for item in data["equipment"]]
