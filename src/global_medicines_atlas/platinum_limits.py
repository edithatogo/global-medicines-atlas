"""Small deterministic controls shared by Platinum read-only surfaces.

The limiter is deliberately process-local.  It is a safety valve for a single
worker, not a claim of distributed quota enforcement; a gateway must enforce
quotas across workers when that is required.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from time import monotonic

_MAX_REQUESTS = 10_000
_MAX_WINDOW_SECONDS = 86_400.0
_MAX_CONSUMERS = 100_000
_MAX_CONSUMER_KEY = 256


class PlatinumRateLimitExceededError(ValueError):
    """Raised when a consumer exceeds its bounded request allowance."""


@dataclass(frozen=True)
class RateLimitPolicy:
    """Fixed-window request policy with explicit, finite bounds."""

    requests: int = 60
    window_seconds: float = 60.0

    def __post_init__(self) -> None:
        if (
            type(self.requests) is not int
            or not 1 <= self.requests <= _MAX_REQUESTS
        ):
            raise ValueError("requests must be between 1 and 10000")
        if (
            type(self.window_seconds) is not float
            or self.window_seconds <= 0
            or self.window_seconds > _MAX_WINDOW_SECONDS
        ):
            raise ValueError("window_seconds must be finite and bounded")


class InMemoryRateLimiter:
    """Deterministic per-consumer fixed-window limiter.

    ``clock`` is injectable for tests and must return a monotonic timestamp.
    State is bounded by ``max_consumers`` and old windows are discarded on
    admission; callers should use a gateway for distributed enforcement.
    """

    def __init__(
        self,
        policy: RateLimitPolicy | None = None,
        *,
        clock: Callable[[], float] = monotonic,
        max_consumers: int = 10_000,
    ) -> None:
        if (
            type(max_consumers) is not int
            or not 1 <= max_consumers <= _MAX_CONSUMERS
        ):
            raise ValueError("max_consumers must be bounded")
        self.policy = policy if policy is not None else RateLimitPolicy()
        self._clock = clock
        self._max_consumers = max_consumers
        self._windows: dict[str, tuple[float, int]] = {}

    def admit(self, consumer: str) -> None:
        """Consume one request slot, rejecting malformed or over-limit keys."""
        if (
            type(consumer) is not str
            or not consumer
            or len(consumer) > _MAX_CONSUMER_KEY
        ):
            raise ValueError("consumer key is invalid")
        now = self._clock()
        if not isfinite(now) or now < 0:
            raise ValueError("clock must return a non-negative finite value")
        current = self._windows.get(consumer)
        if current is None:
            if len(self._windows) >= self._max_consumers:
                raise PlatinumRateLimitExceededError(
                    "consumer capacity exceeded"
                )
            self._windows[consumer] = (float(now), 1)
            return
        started, count = current
        if float(now) - started >= self.policy.window_seconds:
            self._windows[consumer] = (float(now), 1)
            return
        if count >= self.policy.requests:
            raise PlatinumRateLimitExceededError("request rate limit exceeded")
        self._windows[consumer] = (started, count + 1)


__all__ = [
    "InMemoryRateLimiter",
    "PlatinumRateLimitExceededError",
    "RateLimitPolicy",
]
