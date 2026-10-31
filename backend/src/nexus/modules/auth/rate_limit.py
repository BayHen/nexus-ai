"""Bounded in-process authentication rate limiter."""

import asyncio
from collections import defaultdict, deque
from time import monotonic


class AuthenticationRateLimiter:
    """Fixed-window limiter for a single API process.

    A shared Redis limiter is required before horizontal production scaling.
    """

    def __init__(self, attempts: int, window_seconds: int, max_keys: int = 10_000) -> None:
        self._attempts = attempts
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        """Consume an attempt and return whether it is within the configured limit."""
        now = monotonic()
        async with self._lock:
            if key not in self._events and len(self._events) >= self._max_keys:
                self._prune_expired(now)
                if len(self._events) >= self._max_keys:
                    return False
            events = self._events[key]
            while events and now - events[0] >= self._window_seconds:
                events.popleft()
            if len(events) >= self._attempts:
                return False
            events.append(now)
            return True

    def _prune_expired(self, now: float) -> None:
        expired = [
            key
            for key, events in self._events.items()
            if not events or now - events[-1] >= self._window_seconds
        ]
        for key in expired:
            self._events.pop(key, None)

    async def reset(self, key: str) -> None:
        """Clear failures after successful authentication."""
        async with self._lock:
            self._events.pop(key, None)
