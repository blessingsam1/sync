from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic


class RateLimitExceeded(RuntimeError):
    pass


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = monotonic()
        events = self._events[key]
        while events and now - events[0] >= self.window_seconds:
            events.popleft()
        if len(events) >= self.limit:
            raise RateLimitExceeded("Sensitive operation rate limit exceeded")
        events.append(now)

