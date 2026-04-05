from datetime import datetime, timezone, timedelta

import pytest

from api.query_router import Interval, select_interval, validate_range


def _dt(offset_seconds: int) -> datetime:
    return datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )


def test_short_range_uses_raw():
    frm = _dt(0)
    to = _dt(1800)  # 30 min
    assert select_interval(frm, to) == Interval.RAW


def test_medium_range_uses_1min():
    frm = _dt(0)
    to = _dt(7200)  # 2 hours
    assert select_interval(frm, to) == Interval.MIN_1


def test_long_range_uses_1hour():
    frm = _dt(0)
    to = _dt(60 * 60 * 24 * 10)  # 10 days
    assert select_interval(frm, to) == Interval.HOUR_1


def test_boundary_exactly_1_hour_uses_1min():
    frm = _dt(0)
    to = _dt(3600)  # exactly 1 hour
    assert select_interval(frm, to) == Interval.MIN_1


def test_boundary_exactly_7_days_uses_1min():
    frm = _dt(0)
    to = _dt(7 * 24 * 3600)  # exactly 7 days
    assert select_interval(frm, to) == Interval.MIN_1


def test_validate_range_rejects_inverted():
    with pytest.raises(ValueError, match="from must be before to"):
        validate_range(_dt(100), _dt(0))


def test_validate_range_rejects_too_long():
    with pytest.raises(ValueError, match="range too large"):
        validate_range(_dt(0), _dt(60 * 60 * 24 * 100))  # 100 days


def test_validate_range_accepts_valid():
    validate_range(_dt(0), _dt(3600))  # no exception
