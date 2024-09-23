from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketLimiter:
    """Process-local limiter; account identity remains the primary abuse boundary."""

    def __init__(self, *, capacity: int = 30, refill_per_second: float = 0.5) -> None:
        if capacity <= 0 or refill_per_second <= 0:
            raise ValueError("rate limiter parameters must be positive")
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def consume(self, key: str, *, cost: int = 1, now: float | None = None) -> RateLimitDecision:
        if cost <= 0:
            raise ValueError("cost must be positive")
        current_time = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.setdefault(key, _Bucket(float(self.capacity), current_time))
            elapsed = max(0.0, current_time - bucket.updated_at)
            bucket.tokens = min(float(self.capacity), bucket.tokens + elapsed * self.refill_per_second)
            bucket.updated_at = current_time
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return RateLimitDecision(True, int(bucket.tokens), 0)
            wait = int((cost - bucket.tokens) / self.refill_per_second) + 1
            return RateLimitDecision(False, int(bucket.tokens), wait)

    def forget(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {key: int(bucket.tokens) for key, bucket in self._buckets.items()}
