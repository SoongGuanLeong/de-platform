"""Rate limiting and reconnect backoff, driven by an injected clock.

The clock and sleep are injected so a test asserts the computed wait rather
than waiting on wall time (docs/testing-strategy.md section 9).
"""

from __future__ import annotations

import time
from collections.abc import Callable


class RateLimiter:
    """Spaces calls so no two are closer than `min_interval_seconds`."""

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = float(min_interval_seconds)
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> float:
        """Block until the next call is allowed; return the seconds waited."""
        now = self._clock()
        if self._last is None:
            self._last = now
            return 0.0
        delay = self._interval - (now - self._last)
        if delay <= 0:
            self._last = now
            return 0.0
        self._sleep(delay)
        self._last = self._clock()
        return delay


class Backoff:
    """Exponential backoff, capped, with a reset after a healthy period."""

    def __init__(self, base: float, factor: float, max_delay: float) -> None:
        self._base = float(base)
        self._factor = float(factor)
        self._max = float(max_delay)
        self._attempt = 0

    def next(self) -> float:
        delay = min(self._base * (self._factor**self._attempt), self._max)
        self._attempt += 1
        return delay

    def reset(self) -> None:
        self._attempt = 0
