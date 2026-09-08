from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Неблокирующий ограничитель частоты для одного процесса бота."""

    def __init__(self, *, limit: int = 8, window_seconds: float = 2.0) -> None:
        if limit < 1 or window_seconds <= 0:
            raise ValueError("Некорректные параметры ограничителя")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, key: int, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        bucket = self._events[key]
        boundary = current - self.window_seconds
        while bucket and bucket[0] <= boundary:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(current)
        return True
