"""Sliding-window rate limiting. In-memory per process (MVP single-instance);
the interface allows a Redis-backed implementation for multi-instance deployments."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.errors import RateLimited


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, scope: str, key: str, limit: int, window_sec: int) -> None:
        now = time.monotonic()
        dq = self._hits[(scope, key)]
        while dq and now - dq[0] > window_sec:
            dq.popleft()
        if len(dq) >= limit:
            raise RateLimited(
                f"Rate limit exceeded for scope '{scope}' ({limit} per {window_sec}s). Retry shortly.",
                details={"scope": scope, "limit": limit, "window_sec": window_sec, "retry_after_sec": int(window_sec - (now - dq[0])) if dq else window_sec},
            )
        dq.append(now)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()


def limit(scope: str, key: str, limit_: int, window_sec: int) -> None:
    limiter.check(scope, key, limit_, window_sec)
