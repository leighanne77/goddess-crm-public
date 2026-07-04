"""Tests for the per-user chat rate limiter."""

import time
from typing import Generator

import pytest
from fastapi import HTTPException

from app.services import rate_limit
from app.services.rate_limit import check_rate_limit


@pytest.fixture(autouse=True)
def _isolate_rate_limit_state() -> Generator[None, None, None]:
    """Each test starts with empty buckets and the real clock."""
    rate_limit.reset_for_testing()
    rate_limit.set_clock_for_testing(time.monotonic)
    yield
    rate_limit.reset_for_testing()
    rate_limit.set_clock_for_testing(time.monotonic)


def _use_fake_clock(start: float = 1_000_000.0) -> list[float]:
    """Replace the limiter's clock with a controllable list-of-one float."""
    fake = [start]
    rate_limit.set_clock_for_testing(lambda: fake[0])
    return fake


def test_under_limit_passes_silently() -> None:
    for _ in range(60):
        check_rate_limit(user_id=1, limit=60)


def test_over_limit_raises_429() -> None:
    for _ in range(60):
        check_rate_limit(user_id=1, limit=60)
    with pytest.raises(HTTPException) as exc_info:
        check_rate_limit(user_id=1, limit=60)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in exc_info.value.headers


def test_clock_advance_releases_the_limit() -> None:
    fake = _use_fake_clock()
    for _ in range(60):
        check_rate_limit(user_id=1, limit=60)
    with pytest.raises(HTTPException):
        check_rate_limit(user_id=1, limit=60)

    # Advance past the 1-hour window.
    fake[0] += 3601

    check_rate_limit(user_id=1, limit=60)


def test_buckets_are_per_user() -> None:
    for _ in range(60):
        check_rate_limit(user_id=1, limit=60)
    # User 2 should still have a full quota.
    for _ in range(60):
        check_rate_limit(user_id=2, limit=60)
    with pytest.raises(HTTPException):
        check_rate_limit(user_id=1, limit=60)


def test_lockout_does_not_extend_when_attempts_keep_coming() -> None:
    """Failed attempts must NOT consume slots, so the bucket can drain."""
    fake = _use_fake_clock()
    for _ in range(60):
        check_rate_limit(user_id=1, limit=60)

    # Hammer the limiter with 100 failed attempts.
    for _ in range(100):
        with pytest.raises(HTTPException):
            check_rate_limit(user_id=1, limit=60)

    # Advance past the window — the original 60 should have aged out,
    # not the failed attempts.
    fake[0] += 3601
    check_rate_limit(user_id=1, limit=60)
