from datetime import datetime, timezone, timedelta

from ingest.batch_buffer import BatchBuffer, Sample


def _s(t: int) -> Sample:
    return Sample(
        time=datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=t),
        equipment_id="E-01",
        metric_name="temperature",
        value=45.0,
        status="running",
        batch_id="B-1",
        unit_id="U-1",
    )


def test_buffer_starts_empty():
    b = BatchBuffer(max_size=10, max_age_seconds=1.0)
    assert len(b) == 0
    assert not b.should_flush(now=_s(0).time)


def test_flush_on_size():
    b = BatchBuffer(max_size=3, max_age_seconds=10.0)
    for i in range(3):
        b.add(_s(i))
    assert b.should_flush(now=_s(0).time)


def test_flush_on_age():
    b = BatchBuffer(max_size=100, max_age_seconds=1.0)
    b.add(_s(0))
    # Same time: no flush
    assert not b.should_flush(now=_s(0).time)
    # 2 seconds later: flush
    assert b.should_flush(now=_s(2).time)


def test_drain_returns_and_clears():
    b = BatchBuffer(max_size=10, max_age_seconds=10.0)
    b.add(_s(0))
    b.add(_s(1))
    drained = b.drain()
    assert len(drained) == 2
    assert len(b) == 0


def test_bounded_drops_oldest_when_overflow():
    b = BatchBuffer(max_size=3, max_age_seconds=10.0, overflow_limit=5)
    for i in range(7):
        b.add(_s(i))
    assert len(b) == 5  # capped at overflow_limit
    drained = b.drain()
    # Oldest 2 should have been dropped
    assert drained[0].time == _s(2).time
