from pathlib import Path

from api.seed import parse_equipment_yaml

FIXTURE = """
equipment:
  - id: X-01
    name: "Test"
    type: formation_cycler
    location: "A/1"
    metadata: {vendor: Test}
    metrics: [temperature]
    unit_duration_seconds: 60
    unit_id_prefix: CELL
  - id: X-02
    name: "Test 2"
    type: aging_chamber
    location: "A/2"
    metadata: {}
    metrics: [temperature]
    unit_duration_seconds: 3600
    unit_id_prefix: TRAY
"""


def test_parse_equipment_yaml(tmp_path: Path):
    p = tmp_path / "equipment.yaml"
    p.write_text(FIXTURE)
    rows = parse_equipment_yaml(p)
    assert len(rows) == 2
    assert rows[0]["id"] == "X-01"
    assert rows[0]["type"] == "formation_cycler"
    assert rows[0]["metadata"] == {"vendor": "Test"}
    assert rows[1]["id"] == "X-02"
