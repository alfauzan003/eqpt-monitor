from datetime import datetime, timezone

from ingest.redis_publisher import build_publish_payload, build_hot_cache_fields


def test_build_publish_payload():
    t = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    payload = build_publish_payload(
        equipment_id="E-01",
        time=t,
        status="running",
        batch_id="B-1",
        unit_id="U-1",
        metrics={"temperature": 45.2, "voltage": 3.7},
    )
    assert payload["equipment_id"] == "E-01"
    assert payload["time"] == "2026-04-05T12:00:00+00:00"
    assert payload["status"] == "running"
    assert payload["batch_id"] == "B-1"
    assert payload["unit_id"] == "U-1"
    assert payload["metrics"]["temperature"] == 45.2


def test_build_hot_cache_fields():
    t = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
    fields = build_hot_cache_fields(
        status="running",
        batch_id="B-1",
        unit_id="U-1",
        unit_started_at=t,
        metrics={"temperature": 45.2},
        updated_at=t,
    )
    assert fields["status"] == "running"
    assert fields["current_batch_id"] == "B-1"
    assert fields["current_unit_id"] == "U-1"
    assert fields["unit_started_at"] == "2026-04-05T12:00:00+00:00"
    assert fields["temperature"] == "45.2"
    assert fields["updated_at"] == "2026-04-05T12:00:00+00:00"
