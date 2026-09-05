"""Bounded, deterministic Platinum request controls."""

import pytest

from global_medicines_atlas.platinum_limits import (
    InMemoryRateLimiter,
    PlatinumRateLimitExceededError,
    RateLimitPolicy,
)


def test_fixed_window_is_deterministic_and_resets() -> None:
    now = [10.0]
    limiter = InMemoryRateLimiter(
        RateLimitPolicy(requests=2, window_seconds=5.0), clock=lambda: now[0]
    )
    limiter.admit("client")
    limiter.admit("client")
    with pytest.raises(PlatinumRateLimitExceededError):
        limiter.admit("client")
    now[0] = 15.0
    limiter.admit("client")


def test_consumers_are_isolated_and_invalid_policy_fails_closed() -> None:
    with pytest.raises(ValueError, match="requests"):
        RateLimitPolicy(requests=0)
    limiter = InMemoryRateLimiter(RateLimitPolicy(requests=1, window_seconds=1.0))
    limiter.admit("a")
    limiter.admit("b")
    with pytest.raises(ValueError, match="consumer key"):
        limiter.admit("")
