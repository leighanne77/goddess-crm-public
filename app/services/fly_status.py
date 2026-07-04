"""Single source of truth for the fly_status tiers.

`fly_status` is referenced in three places that must agree:
  - the `FlyStatus` Literal Claude sees      (app/services/tools.py)
  - the affinity weights the engine scores   (app/services/intro_paths.py)
  - the search sort order                     (app/services/tool_dispatch.py)

Defining the tiers — and their warmth and ordering — here keeps those
three from drifting when a tier is added or renamed. The `FlyStatus`
Literal can't be generated from this at type-check time (typing
limitation), so it stays spelled out in tools.py; `test_fly_status.py`
guards that it still matches this set.

Pure module: no database, no model imports. The intro engine can import
it without giving up its DB-free guarantee.
"""

from __future__ import annotations

# Canonical order: warmest / highest-priority first. This tuple IS the
# search sort order (index = rank). "Off Fly List" stays visible but
# sorts last; it's gated out of intro paths entirely by the engine.
FLY_STATUS_ORDER: tuple[str, ...] = (
    "Must Fly",
    "Fly List",
    "Maybe Must Fly",
    "Unknown",
    "Off Fly List",
)

# Our-side warmth per tier, in [0, 1] — the affinity the intro engine
# multiplies in. "Off Fly List" is gated out before this is read; its
# 0.0 is belt-and-braces. Keys must match FLY_STATUS_ORDER exactly
# (guarded by test_fly_status.py).
FLY_STATUS_AFFINITY: dict[str, float] = {
    "Must Fly": 1.0,
    "Fly List": 0.75,
    "Maybe Must Fly": 0.5,
    "Unknown": 0.25,
    "Off Fly List": 0.0,
}

# Legacy labels still on some pre-migration rows, mapped to their modern
# tier. Applied for both affinity and search ordering so old rows behave
# like the tier they were renamed to.
LEGACY_FLY_STATUS_ALIASES: dict[str, str] = {"Not Sure Yet": "Maybe Must Fly"}

# The one tier that bars a contact from being an intro intermediary.
BLOCKLIST_FLY_STATUS: str = "Off Fly List"

# Search rank for any value not in the order (shouldn't happen, but keeps
# ORDER BY total): sorts after every known tier.
_UNKNOWN_RANK: int = len(FLY_STATUS_ORDER) + 1


def _canonical(fly_status: str) -> str:
    """Resolve a legacy label to its modern tier; pass others through."""
    return LEGACY_FLY_STATUS_ALIASES.get(fly_status, fly_status)


def affinity_for(fly_status: str) -> float:
    """Our-side warmth for a fly_status, in [0, 1]. Legacy labels resolve
    to their modern tier; anything unknown is treated as cold (0.0)."""
    return FLY_STATUS_AFFINITY.get(_canonical(fly_status), 0.0)


def fly_status_search_priority() -> dict[str, int]:
    """`{fly_status: rank}` for ORDER BY — lower rank shows first. Ranks
    follow FLY_STATUS_ORDER (1-based); legacy aliases share their modern
    tier's rank. Unknown values fall back to a trailing rank via the
    `else_` on the SQL `case()` (see tool_dispatch)."""
    pri = {status: i + 1 for i, status in enumerate(FLY_STATUS_ORDER)}
    for legacy, modern in LEGACY_FLY_STATUS_ALIASES.items():
        pri[legacy] = pri[modern]
    return pri


def unknown_search_rank() -> int:
    """The `else_` rank for `case()` — sorts unrecognized statuses last."""
    return _UNKNOWN_RANK
