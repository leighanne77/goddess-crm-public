"""Per-user rate limiter for the chat endpoint.

In-memory only — Phase 1 single-server setup. Phase 2 swaps for Redis
when restart survival or multi-instance support is needed.

Counts only attempts that pass the limit check, so being rate-limited
does not extend the lockout — old timestamps still age out and capacity
returns naturally as the window slides forward.
"""

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable, Final

from fastapi import Depends, HTTPException, status

from app.config import get_settings
from app.dependencies import get_current_user
from app.models import User

_HOUR_SECONDS: Final = 3600

_chat_requests: defaultdict[int, deque[float]] = defaultdict(deque)
_lock = Lock()
_now_fn: Callable[[], float] = time.monotonic


def _resolve_limit(current_user: User) -> int:
    if current_user.rate_limit_per_hour_override is not None:
        return current_user.rate_limit_per_hour_override
    return get_settings().chat_rate_limit_per_hour


def check_rate_limit(
    user_id: int, limit: int, window_seconds: int = _HOUR_SECONDS
) -> None:
    """Record a request and raise 429 if the user is over the cap."""
    now = _now_fn()
    cutoff = now - window_seconds
    with _lock:
        bucket = _chat_requests[user_id]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(int(bucket[0] + window_seconds - now), 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Chat rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def enforce_chat_rate_limit(
    current_user: User = Depends(get_current_user),
) -> None:
    """FastAPI dependency: 429 if the user is over their hourly chat cap."""
    check_rate_limit(current_user.id, _resolve_limit(current_user))


def reset_for_testing() -> None:
    """Clear all rate-limit buckets. Tests only."""
    with _lock:
        _chat_requests.clear()


def set_clock_for_testing(clock: Callable[[], float]) -> None:
    """Replace the time source. Tests only."""
    global _now_fn
    _now_fn = clock
