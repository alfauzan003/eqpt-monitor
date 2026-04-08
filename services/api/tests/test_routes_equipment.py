from api.routes.equipment import _split_latest


def test_split_latest_separates_meta_from_metrics():
    h = {
        "status": "running",
        "current_batch_id": "B-1",
        "current_unit_id": "U-1",
        "unit_started_at": "2026-04-05T12:00:00+00:00",
        "updated_at": "2026-04-05T12:00:01+00:00",
        "temperature": "45.2",
        "voltage": "3.7",
    }
    meta, metrics = _split_latest(h)
    assert meta["status"] == "running"
    assert meta["current_batch_id"] == "B-1"
    assert metrics == {"temperature": 45.2, "voltage": 3.7}


def test_split_latest_handles_empty():
    meta, metrics = _split_latest({})
    assert meta == {
        "status": None,
        "current_batch_id": None,
        "current_unit_id": None,
        "unit_started_at": None,
        "updated_at": None,
    }
    assert metrics == {}


def test_split_latest_skips_non_numeric_metrics():
    h = {"status": "running", "temperature": "not_a_number"}
    _, metrics = _split_latest(h)
    assert metrics == {}
