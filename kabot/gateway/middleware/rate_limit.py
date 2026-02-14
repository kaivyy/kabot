"""Token-bucket rate limiter for gateway requests."""

import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_tokens: int = 5, refill_rate: float = 1.0):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate  # tokens per second
        self._buckets: dict[str, tuple[float, float]] = defaultdict(
            lambda: (float(max_tokens), time.time())
        )

    def allow(self, key: str) -> bool:
        tokens, last_refill = self._buckets[key]
        now = time.time()
        elapsed = now - last_refill
        tokens = min(self.max_tokens, tokens + elapsed * self.refill_rate)
        if tokens >= 1:
            self._buckets[key] = (tokens - 1, now)
            return True
        self._buckets[key] = (tokens, now)
        return False
