"""Phase 5 Slice 2 — unit tests for the deterministic intro-path engine.

Pure functions, no DB. Proves the gates, affinity mapping, sector
overlap, connection strength, path scoring, and ranking behave exactly
as specified before Slice 3 wires them to the relationships graph.
"""

import pytest

from app.services.intro_paths import (
    ContactNode,
    IntroPath,
    affinity,
    connection_strength,
    gate_reason,
    is_geographically_close,
    rank_paths,
    score_path,
    sector_overlap,
)


def _node(
    name: str,
    *,
    fly: str = "Must Fly",
    opt: str = "APPROVED",
    sectors: tuple[str, ...] = (),
    metro: str = "",
    cid: int = 0,
) -> ContactNode:
    return ContactNode(
        contact_id=cid,
        name=name,
        fly_status=fly,
        opt_in_status=opt,
        sectors=sectors,
        metro=metro,
    )


# --- affinity ----------------------------------------------------------


def test_affinity_maps_fly_tiers() -> None:
    assert affinity("Must Fly") == 1.0
    assert affinity("Fly List") == 0.75
    assert affinity("Maybe Must Fly") == 0.5
    assert affinity("Unknown") == 0.25
    assert affinity("Off Fly List") == 0.0


def test_affinity_unknown_status_is_cold_not_error() -> None:
    assert affinity("Totally Made Up") == 0.0


# --- gates -------------------------------------------------------------


def test_gate_blocklist_first() -> None:
    assert gate_reason("Off Fly List", "APPROVED") == "blocklisted (Off Fly List)"


def test_gate_opt_in_pending_and_denied() -> None:
    assert gate_reason("Must Fly", "PENDING") == "opt-in pending"
    assert gate_reason("Must Fly", "DENIED") == "opt-in denied"


def test_gate_passes_for_approved_non_blocklisted() -> None:
    assert gate_reason("Must Fly", "APPROVED") is None


# --- sector overlap ----------------------------------------------------


def test_sector_overlap_jaccard() -> None:
    assert sector_overlap(("Maritime", "Energy"), ("Maritime",)) == 0.5


def test_sector_overlap_disjoint_and_empty() -> None:
    assert sector_overlap(("Maritime",), ("Energy",)) == 0.0
    assert sector_overlap((), ("Energy",)) == 0.0


def test_sector_overlap_is_case_insensitive() -> None:
    assert sector_overlap(("Maritime",), ("maritime",)) == 1.0


# --- connection strength ----------------------------------------------


def test_connection_strength_weights() -> None:
    # 0.45 * 0.5 (sector) + 0.35 * 1.0 (strong) = 0.575
    assert connection_strength(
        ("Maritime", "Energy"), ("Maritime",), "strong"
    ) == pytest.approx(0.575)
    # 0.45 * 0.5 + 0.35 * 0.5 = 0.4
    assert connection_strength(
        ("Maritime", "Energy"), ("Maritime",), "some"
    ) == pytest.approx(0.4)
    # no overlap, no history, no shared metro → 0
    assert connection_strength(("Maritime",), ("Energy",), "none") == 0.0


# --- geography ---------------------------------------------------------


def test_is_geographically_close() -> None:
    assert is_geographically_close("Mobile", "mobile") is True
    assert is_geographically_close("Mobile", "Houston") is False
    assert is_geographically_close("", "Mobile") is False


def test_connection_adds_geography_for_same_metro() -> None:
    # same metro adds W_GEO (0.20): 0.45*1.0 (sector) + 0 + 0.20*1 = 0.65
    same = connection_strength(("Maritime",), ("Maritime",), "none", "Mobile", "Mobile")
    diff = connection_strength(
        ("Maritime",), ("Maritime",), "none", "Mobile", "Houston"
    )
    assert same == pytest.approx(0.65)
    assert diff == pytest.approx(0.45)
    assert same > diff


# --- path scoring ------------------------------------------------------


def test_score_single_hop_path() -> None:
    a = _node("Ada", fly="Must Fly", sectors=("Maritime", "Energy"))
    t = _node("Target", sectors=("Maritime",))
    path = IntroPath(intermediaries=(a,), target=t, hop_histories=("strong",))

    result = score_path(path)
    assert result.gated_reason is None
    assert result.affinity == 1.0
    # 0.45 * 0.5 (sector) + 0.35 * 1.0 (strong) = 0.575
    assert result.connection == pytest.approx(0.575)
    assert result.degrees == 1
    assert result.score == pytest.approx(0.575)


def test_score_two_hop_path_uses_first_intermediary_affinity() -> None:
    a = _node("Ada", fly="Fly List", sectors=("Maritime",))
    b = _node("Ben", fly="Must Fly", sectors=("Energy",))
    t = _node("Target", sectors=("Energy",))
    path = IntroPath(intermediaries=(a, b), target=t, hop_histories=("some", "strong"))

    result = score_path(path)
    # affinity = first intermediary (Ada, Fly List) = 0.75
    assert result.affinity == 0.75
    # A->B: 0.45*0 + 0.35*0.5 = 0.175 ; B->T: 0.45*1 + 0.35*1 = 0.8 ; product 0.14
    assert result.connection == pytest.approx(0.14)
    assert result.degrees == 2
    # 0.75 * 0.14 / 2
    assert result.score == pytest.approx(0.0525)


def test_gated_intermediary_discards_path() -> None:
    a = _node("Ada", fly="Must Fly")
    blocked = _node("Ben", opt="PENDING")
    t = _node("Target")
    path = IntroPath(
        intermediaries=(a, blocked), target=t, hop_histories=("some", "some")
    )

    result = score_path(path)
    assert result.score == 0.0
    assert result.gated_reason == "Ben: opt-in pending"


def test_blocklisted_intermediary_discards_path() -> None:
    blocked = _node("Cyd", fly="Off Fly List")
    t = _node("Target")
    path = IntroPath(intermediaries=(blocked,), target=t, hop_histories=("strong",))
    assert score_path(path).gated_reason == "Cyd: blocklisted (Off Fly List)"


def test_empty_path_is_gated() -> None:
    t = _node("Target")
    path = IntroPath(intermediaries=(), target=t, hop_histories=())
    assert score_path(path).gated_reason == "no intermediary"


# --- ranking -----------------------------------------------------------


def test_rank_drops_gated_and_sorts_best_first() -> None:
    t = _node("Target", sectors=("Maritime",))

    strong = IntroPath(
        intermediaries=(_node("Ada", fly="Must Fly", sectors=("Maritime",)),),
        target=t,
        hop_histories=("strong",),
    )  # 1.0 * (0.45 + 0.35) / 1 = 0.8
    weak = IntroPath(
        intermediaries=(_node("Ben", fly="Unknown", sectors=("Maritime",)),),
        target=t,
        hop_histories=("none",),
    )  # 0.25 * 0.45 / 1 = 0.1125
    gated = IntroPath(
        intermediaries=(_node("Cyd", opt="DENIED", sectors=("Maritime",)),),
        target=t,
        hop_histories=("strong",),
    )

    ranked = rank_paths([weak, gated, strong])
    assert [r.path.intermediaries[0].name for r in ranked] == ["Ada", "Ben"]
    assert ranked[0].score == pytest.approx(0.8)
    assert ranked[1].score == pytest.approx(0.1125)
