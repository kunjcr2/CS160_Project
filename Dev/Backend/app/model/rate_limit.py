"""In-memory per-IP rate limit for brute-force-prone auth endpoints.

No external store (no Redis): a dict of recent attempt timestamps per key,
pruned to a sliding window on each check. Fine for a single-process app;
would need a shared store (e.g. Redis) behind multiple instances.
"""

import math
import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.config import settings
from app.views import messages


class RateLimiter:
    """Allows at most `max_attempts` calls per key within `window_seconds`."""

    def __init__(
        self,
        max_attempts: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        """Record an attempt for `key`; raise HTTPException(429) once over the limit."""
        now = self._clock()
        window_start = now - self._window_seconds
        recent = [t for t in self._attempts[key] if t > window_start]
        if len(recent) >= self._max_attempts:
            self._attempts[key] = recent
            # recent[0] is the oldest attempt still in the window; the caller may
            # retry once it ages out.
            retry_after = max(1, math.ceil(recent[0] + self._window_seconds - now))
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                messages.TOO_MANY_ATTEMPTS,
                headers={"Retry-After": str(retry_after)},
            )
        recent.append(now)
        self._attempts[key] = recent

    def reset(self) -> None:
        """Clear all recorded attempts. Tests use this so state doesn't leak between tests."""
        self._attempts.clear()


# One shared limiter for the whole app process.
_auth_rate_limiter = RateLimiter(
    settings.rate_limit_max_attempts, settings.rate_limit_window_seconds
)


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency: 429s once the caller's IP exceeds the configured attempt limit."""
    ip = request.client.host if request.client else "unknown"
    _auth_rate_limiter.check(ip)


def reset_rate_limit_store() -> None:
    """Clear the shared limiter's state. Call between tests so attempts don't carry over."""
    _auth_rate_limiter.reset()
