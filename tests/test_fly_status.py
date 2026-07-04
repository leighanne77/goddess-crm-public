"""Guards the single source of truth for fly_status tiers.

The point of app/services/fly_status is that the FlyStatus Literal Claude
sees, the engine's affinity weights, and the search sort order can't
drift. These tests fail loudly the moment one of them gains or loses a
tier without the others — which is the whole reason the module exists.
"""

from typing import get_args

from app.services.fly_status import (
    BLOCKLIST_FLY_STATUS,
    FLY_STATUS_AFFINITY,
    FLY_STATUS_ORDER,
    LEGACY_FLY_STATUS_ALIASES,
    affinity_for,
    fly_status_search_priority,
    unknown_search_rank,
)
from app.services.intro_paths import affinity
from app.services.tools import FlyStatus


def test_literal_matches_canonical_order() -> None:
    # The Claude-facing Literal must cover exactly the canonical tiers.
    assert set(get_args(FlyStatus)) == set(FLY_STATUS_ORDER)


def test_affinity_keys_match_canonical_order() -> None:
    assert set(FLY_STATUS_AFFINITY) == set(FLY_STATUS_ORDER)


def test_search_priority_covers_every_tier_and_legacy_alias() -> None:
    pri = fly_status_search_priority()
    # Every canonical tier is ranked, 1-based, in order.
    for i, status in enumerate(FLY_STATUS_ORDER):
        assert pri[status] == i + 1
    # Legacy aliases share their modern tier's rank.
    for legacy, modern in LEGACY_FLY_STATUS_ALIASES.items():
        assert pri[legacy] == pri[modern]
    # The else_ rank sorts after every known tier.
    assert unknown_search_rank() > max(pri.values())


def test_blocklist_tier_is_a_real_tier() -> None:
    assert BLOCKLIST_FLY_STATUS in FLY_STATUS_ORDER


def test_affinity_for_preserves_known_values() -> None:
    assert affinity_for("Must Fly") == 1.0
    assert affinity_for("Off Fly List") == 0.0
    # Legacy label resolves to its modern tier's warmth.
    assert affinity_for("Not Sure Yet") == affinity_for("Maybe Must Fly")
    # Anything unrecognized is cold, never raises.
    assert affinity_for("Nonsense") == 0.0


def test_engine_affinity_delegates_to_shared_helper() -> None:
    # intro_paths.affinity is now a thin alias — same answers as the source.
    for status in (*FLY_STATUS_ORDER, *LEGACY_FLY_STATUS_ALIASES):
        assert affinity(status) == affinity_for(status)


def test_warmth_guardrail_affinity_strictly_decreases_by_tier() -> None:
    """Warmth guardrail: fly_status dominates recency.

    A Must Fly contact is warmer than any non-Must-Fly, even if not recently
    used. The backbone of that rule is that affinity is *strictly* ordered by
    fly_status tier (FLY_STATUS_ORDER, warmest first). This invariant is what
    will let a future recency / interaction-health signal (Engine v2) act only
    as a bounded, within-tier nudge — it can re-order within a tier but can
    never promote a lower tier above a higher one. If this ever fails, the
    warmth ordering has silently broken. See docs/Context_Mngmt/guardrails.md.
    """
    vals = [FLY_STATUS_AFFINITY[s] for s in FLY_STATUS_ORDER]
    # Strictly decreasing: each tier is genuinely warmer than the next.
    assert all(a > b for a, b in zip(vals, vals[1:])), vals
    # The gap between adjacent tiers bounds how much a within-tier recency
    # nudge may move a score without crossing a tier boundary.
    assert min(a - b for a, b in zip(vals, vals[1:])) > 0.0
