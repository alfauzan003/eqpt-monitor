"""Buffered telemetry samples, flushed on size or age."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Sample:
    time: datetime
    equipment_id: str
    metric_name: str
    value: float
    status: str | None
    batch_id: str | None
    unit_id: str | None


class BatchBuffer:
    def __init__(
        self,
        max_size: int,
        max_age_seconds: float,
        overflow_limit: int | None = None,
    ) -> None:
        self._max_size = max_size
        self._max_age = timedelta(seconds=max_age_seconds)
        self._overflow_limit = overflow_limit or (max_size * 100)
        self._buf: deque[Sample] = deque()
        self._oldest_time: datetime | None = None

    def add(self, sample: Sample) -> None:
        if self._oldest_time is None:
            self._oldest_time = sample.time
        self._buf.append(sample)
        while len(self._buf) > self._overflow_limit:
            self._buf.popleft()
            self._oldest_time = self._buf[0].time if self._buf else None

    def should_flush(self, now: datetime) -> bool:
        if len(self._buf) == 0:
            return False
        if len(self._buf) >= self._max_size:
            return True
        if self._oldest_time is not None and (now - self._oldest_time) >= self._max_age:
            return True
        return False

    def drain(self) -> list[Sample]:
        out = list(self._buf)
        self._buf.clear()
        self._oldest_time = None
        return out

    def __len__(self) -> int:
        return len(self._buf)
