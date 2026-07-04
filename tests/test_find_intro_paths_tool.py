"""Phase 5 Slice 4 — tests for the find_intro_paths chat tool.

The pathfinder service itself is covered in test_intro_pathfinder.py.
These tests cover the dispatch wrapper: schema validation, the JSON
shape Claude reads back, and that the privacy/gate behavior surfaces as
the right tool result (not_found vs empty paths).
"""

from typing import Callable

import pytest
from sqlalchemy.orm import Session

from app.models import Contact, Relationship, User
from app.services.tool_dispatch import ToolDispatchError, dispatch_tool_call


def _contact(
    db: Session,
    owner: User,
    name: str,
    *,
    fly: str = "Must Fly",
    opt: str = "APPROVED",
    sectors: tuple[str, ...] = (),
    private: bool = False,
) -> Contact:
    c = Contact(
        name=name,
        owner_id=owner.id,
        fly_status=fly,
        opt_in_status=opt,
        sectors=list(sectors),
        is_private=private,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _edge(db: Session, a: Contact, b: Contact, *, hist: str = "strong") -> None:
    db.add(Relationship(from_contact_id=a.id, to_contact_id=b.id, shared_history=hist))
    db.commit()


def test_returns_ranked_path_shape(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    ada = _contact(db, me, "Ada", sectors=("Maritime",))
    target = _contact(db, me, "Barrett", sectors=("Maritime",))
    _edge(db, ada, target, hist="strong")

    result = dispatch_tool_call(
        "find_intro_paths", {"target_contact_id": target.id}, me, db
    )

    assert result["target"] == {"id": target.id, "name": "Barrett"}
    assert result["count"] == 1
    path = result["paths"][0]
    assert path["reach_out_to"]["name"] == "Ada"
    assert path["reach_out_to"]["fly_status"] == "Must Fly"
    assert path["chain"] == ["Ada", "Barrett"]
    assert path["hops"] == 1
    assert path["score"] > 0


def test_warmest_path_first(db: Session, user_factory: Callable[..., User]) -> None:
    me = user_factory()
    target = _contact(db, me, "Barrett", sectors=("Maritime",))
    _contact(db, me, "Ada", fly="Must Fly", sectors=("Maritime",))
    _contact(db, me, "Cyd", fly="Unknown", sectors=("Energy",))
    ada = db.query(Contact).filter_by(name="Ada").one()
    cyd = db.query(Contact).filter_by(name="Cyd").one()
    _edge(db, ada, target, hist="strong")
    _edge(db, cyd, target, hist="none")

    result = dispatch_tool_call(
        "find_intro_paths", {"target_contact_id": target.id}, me, db
    )
    # Ada (Must Fly, sector + history match) ranks ahead of Cyd.
    assert result["paths"][0]["reach_out_to"]["name"] == "Ada"


def test_target_not_visible_is_not_found(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    other = user_factory()
    hidden = _contact(db, other, "Secret", private=True)

    result = dispatch_tool_call(
        "find_intro_paths", {"target_contact_id": hidden.id}, me, db
    )
    assert result["error"] == "not_found"


def test_visible_target_no_route_returns_empty_not_error(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    # Target is visible but the only intermediary is not opted in → gated.
    ada = _contact(db, me, "Ada", opt="PENDING")
    target = _contact(db, me, "Barrett")
    _edge(db, ada, target)

    result = dispatch_tool_call(
        "find_intro_paths", {"target_contact_id": target.id}, me, db
    )
    assert "error" not in result
    assert result["target"]["name"] == "Barrett"
    assert result["count"] == 0
    assert result["paths"] == []


def test_max_results_caps_returned_paths(
    db: Session, user_factory: Callable[..., User]
) -> None:
    me = user_factory()
    target = _contact(db, me, "Barrett", sectors=("Maritime",))
    for i in range(4):
        inter = _contact(db, me, f"Person{i}", sectors=("Maritime",))
        _edge(db, inter, target, hist="strong")

    result = dispatch_tool_call(
        "find_intro_paths",
        {"target_contact_id": target.id, "max_results": 2},
        me,
        db,
    )
    assert result["count"] == 2


def test_bad_target_id_raises(db: Session, user_factory: Callable[..., User]) -> None:
    me = user_factory()
    with pytest.raises(ToolDispatchError, match="Invalid params"):
        dispatch_tool_call("find_intro_paths", {"target_contact_id": 0}, me, db)
