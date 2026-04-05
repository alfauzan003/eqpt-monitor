"""Generate batch_id and unit_id per equipment over time."""
from __future__ import annotations

from datetime import datetime


_UNITS_PER_BATCH = 10


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


class BatchTracker:
    def __init__(
        self,
        unit_duration_seconds: int,
        unit_id_prefix: str,
        now: datetime,
    ) -> None:
        self._unit_duration = unit_duration_seconds
        self._prefix = unit_id_prefix
        self._unit_seq = 0
        self._batch_seq = 0
        self._units_in_current_batch = 0

        self.current_batch_id: str = self._next_batch_id(now)
        self.current_unit_id: str = self._next_unit_id(now)
        self.unit_started_at: datetime = now

    def advance(self, now: datetime) -> None:
        elapsed = (now - self.unit_started_at).total_seconds()
        if elapsed < self._unit_duration:
            return

        # Rotate unit
        self._units_in_current_batch += 1
        if self._units_in_current_batch >= _UNITS_PER_BATCH:
            self.current_batch_id = self._next_batch_id(now)
            self._units_in_current_batch = 0
        self.current_unit_id = self._next_unit_id(now)
        self.unit_started_at = now

    def _next_unit_id(self, now: datetime) -> str:
        self._unit_seq += 1
        return f"{self._prefix}-{_fmt_date(now)}-{self._unit_seq:04d}"

    def _next_batch_id(self, now: datetime) -> str:
        self._batch_seq += 1
        return f"BATCH-{_fmt_date(now)}-{self._batch_seq:03d}"
