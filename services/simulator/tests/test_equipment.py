from pathlib import Path

import pytest

from simulator.config import load_equipment_config, EquipmentConfig


FIXTURE = """
equipment:
  - id: FORM-01
    name: "Formation Cycler #1"
    type: formation_cycler
    location: "Line-A / Bay-1"
    metadata: {vendor: SimuCorp}
    metrics: [temperature, voltage]
    unit_duration_seconds: 1800
    unit_id_prefix: CELL
"""


def test_load_equipment_config(tmp_path: Path):
    p = tmp_path / "equipment.yaml"
    p.write_text(FIXTURE)
    configs = load_equipment_config(p)
    assert len(configs) == 1
    assert configs[0].id == "FORM-01"
    assert configs[0].type == "formation_cycler"
    assert configs[0].metrics == ["temperature", "voltage"]
    assert configs[0].unit_duration_seconds == 1800
    assert configs[0].unit_id_prefix == "CELL"


def test_load_equipment_config_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_equipment_config(tmp_path / "nope.yaml")


def test_equipment_config_round_trip():
    c = EquipmentConfig(
        id="X-01",
        name="Test",
        type="formation_cycler",
        location="A/1",
        metadata={"vendor": "Test"},
        metrics=["temperature"],
        unit_duration_seconds=60,
        unit_id_prefix="CELL",
    )
    assert c.id == "X-01"
