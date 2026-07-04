"""Phase 5 Slice 3 — tests for the warm-introduction pathfinder.

Seeds a small relationship graph and proves the pathfinder finds 1- and
2-hop routes, respects the privacy filter (never routes through a contact
the requester can't see), honors the opt-in / blocklist gates, and ranks
best-first.
"""

from typing import Callable

from sqlalchemy.orm import Session

from app.models import Contact, Relationship, User
from app.services.intro_pathfinder import find_intro_paths


def _contact(
    db: Session,
    owner: User,
    name: str,
    *,
    fly: str = "Must Fly",
    opt: str = "APPROVED",
    sectors: tuple[str, ...] = (),
    metro: str = "",
    private: bool = False,
) -> Contact:
    c = Contact(
        name=name,
        owner_id=owner.id,
        fly_status=fly,
        opt_in_status=opt,
        sectors=list(sectors),
        metro=metro,
        is_private=private,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _edge(db: Session, a: Contact, b: Contact, *, hist: str = "strong") -> Relationship:
    r = Relationship(from_contact_id=a.id, to_contact_id=b.id, shared_history=hist)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_one_hop_path(db: Session, user_factory: Callable[..., User]) -> None:
    me = user_factory()
    ada = _contact(db, me, "Ada", sectors=("Maritime",))
    target = _contact(db, me, "Barrett", sectors=("Maritime",))
    _edge(db, ada, target, hist="strong")

    result = find_intro_paths(db, me, target.id)

    assert result.target is not None and result.target.name == "Barrett"
    assert len(result.paths) == 1
    p = result.paths[0]
    assert [n.name for n in p.path.intermediaries] == ["Ada"]
    assert p.degrees == 1
    assert p.gated_reason is None


def test_two_hop_path(db: Session, user_factory: Callable[..., User]) -> None:
    me = user_factory()
    ada = _contact(db, me, "Ada", sectors=("Maritime",))
    ben = _contact(db, me, "Ben", sectors=("Maritime",))
    target = _contact(db, me, "Barrett", sectors=("Maritime",))
    _edge(db, ada, ben, hist="strong")
    _edge(db, ben, target, hist="strong")  # no direct Ada–Barrett edge

    result = find_intro_paths(db, me, target.id)

    names = [[n.name for n in p.path.intermediaries] for p in result.paths]
    assert ["Ada", "Ben"] in names  # routed Ada -> Ben -> Barrett


def test_pending_optin_intermediary_is_dropped(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    # Default opt_in is PENDING — not approved for intros.
    ada = _contact(db, me, "Ada", opt="PENDING")
    target = _contact(db, me, "Barrett")
    _edge(db, ada, target)

    result = find_intro_paths(db, me, target.id)
    assert result.target is not None
    assert result.paths == []  # the only route is gated out


def test_blocklisted_intermediary_is_dropped(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    ada = _contact(db, me, "Ada", fly="Off Fly List")
    target = _contact(db, me, "Barrett")
    _edge(db, ada, target)

    assert find_intro_paths(db, me, target.id).paths == []


def test_privacy_gate_blocks_route_through_invisible_contact(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    other = user_factory()
    ada = _contact(db, me, "Ada")
    target = _contact(db, me, "Barrett")
    # Mid is private and owned by someone else → invisible to me.
    mid = _contact(db, other, "Mid", private=True)
    _edge(db, ada, mid)
    _edge(db, mid, target)

    # Only route is Ada -> Mid -> Barrett, but Mid is invisible → no path.
    result = find_intro_paths(db, me, target.id)
    assert result.target is not None and result.target.name == "Barrett"
    assert result.paths == []


def test_target_not_visible_returns_no_target(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    other = user_factory()
    hidden_target = _contact(db, other, "Secret", private=True)

    result = find_intro_paths(db, me, hidden_target.id)
    assert result.target is None
    assert result.paths == []


def test_ranks_stronger_path_first(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    target = _contact(db, me, "Barrett", sectors=("Maritime",))
    strong = _contact(db, me, "Ada", fly="Must Fly", sectors=("Maritime",))
    weak = _contact(db, me, "Cyd", fly="Unknown", sectors=("Energy",))
    _edge(db, strong, target, hist="strong")
    _edge(db, weak, target, hist="none")

    result = find_intro_paths(db, me, target.id)
    assert result.paths[0].path.intermediaries[0].name == "Ada"
    assert result.paths[0].score > result.paths[-1].score
