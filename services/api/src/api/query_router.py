"""Select raw / 1-min / 1-hour table based on time range."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

MAX_RANGE_DAYS = 90


class Interval(str, Enum):
    RAW = "raw"
    MIN_1 = "1min"
    HOUR_1 = "1hour"


def select_interval(frm: datetime, to: datetime) -> Interval:
    span = to - frm
    if span < timedelta(hours=1):
        return Interval.RAW
    if span <= timedelta(days=7):
        return Interval.MIN_1
    return Interval.HOUR_1


def validate_range(frm: datetime, to: datetime) -> None:
    if frm >= to:
        raise ValueError("from must be before to")
    if to - frm > timedelta(days=MAX_RANGE_DAYS):
        raise ValueError(f"range too large (max {MAX_RANGE_DAYS} days)")
