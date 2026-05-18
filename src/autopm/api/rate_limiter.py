"""rate_limiter — API 게이트웨이용 스텁."""

from __future__ import annotations

import time
from collections import defaultdict


class InMemoryRateLimiter:
    """프로세스 내 카운터 — Redis 기반으로 갈아끼울 수 있게 클래스로 둔다."""

    def __init__(self, max_per_minute: int = 120) -> None:
        self.max_per_minute = max_per_minute
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        window = now - 60
        arr = [t for t in self._buckets[key] if t > window]
        arr.append(now)
        self._buckets[key] = arr
        return len(arr) <= self.max_per_minute
