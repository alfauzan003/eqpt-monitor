from datetime import datetime, timezone, timedelta

from simulator.batch_tracker import BatchTracker


def _dt(seconds: int = 0) -> datetime:
    return datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_starts_with_initial_batch_and_unit():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    assert t.current_batch_id is not None
    assert t.current_unit_id is not None
    assert t.current_unit_id.startswith("CELL-")


def test_advance_before_duration_no_change():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    first_unit = t.current_unit_id
    t.advance(_dt(30))
    assert t.current_unit_id == first_unit


def test_advance_past_duration_rotates_unit():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    first_unit = t.current_unit_id
    t.advance(_dt(61))
    assert t.current_unit_id != first_unit
    assert t.current_unit_id.startswith("CELL-")


def test_batch_rotates_after_10_units():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    first_batch = t.current_batch_id
    for i in range(1, 11):
        t.advance(_dt(i * 61))
    # After 10 unit rotations, batch should have rotated
    assert t.current_batch_id != first_batch


def test_unit_started_at_updated_on_rotation():
    t = BatchTracker(unit_duration_seconds=60, unit_id_prefix="CELL", now=_dt(0))
    t.advance(_dt(61))
    assert t.unit_started_at >= _dt(60)
