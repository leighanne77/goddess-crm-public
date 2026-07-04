"""Phase 5 — tests for the link_contacts edge-creation tool.

Covers the dispatch handler: edge creation + audit, idempotent upsert,
soft-delete revival, the same-contact guard, and the privacy gate (both
endpoints must be visible to the caller).
"""

from typing import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Contact, Relationship, User
from app.services.tool_dispatch import ToolDispatchError, dispatch_tool_call


def _make_contact(
    db: Session, owner: User, name: str, *, is_private: bool = False
) -> Contact:
    contact = Contact(name=name, owner_id=owner.id, is_private=is_private)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _edges(db: Session) -> list[Relationship]:
    return list(db.scalars(select(Relationship)))


def test_link_creates_edge_and_audit_row(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    a = _make_contact(db, user, "Ada")
    b = _make_contact(db, user, "Ben")

    result = dispatch_tool_call(
        "link_contacts",
        {
            "from_contact_id": a.id,
            "to_contact_id": b.id,
            "relationship_type": "colleague",
            "shared_history": "strong",
        },
        user,
        db,
    )

    assert result["linked"]["created"] is True
    assert result["linked"]["from"]["name"] == "Ada"
    assert result["linked"]["to"]["name"] == "Ben"

    edges = _edges(db)
    assert len(edges) == 1
    assert edges[0].relationship_type == "colleague"
    assert edges[0].shared_history == "strong"
    assert edges[0].source == "manual"
    assert edges[0].created_by_user_id == user.id

    audit = list(db.scalars(select(AuditLog).where(AuditLog.action == "link_contacts")))
    assert len(audit) == 1
    assert audit[0].target_type == "relationship"
    assert audit[0].target_id == edges[0].id


def test_link_same_contact_rejected(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    a = _make_contact(db, user, "Ada")
    with pytest.raises(ToolDispatchError, match="Invalid params"):
        dispatch_tool_call(
            "link_contacts",
            {"from_contact_id": a.id, "to_contact_id": a.id},
            user,
            db,
        )


def test_link_is_idempotent_upsert(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    a = _make_contact(db, user, "Ada")
    b = _make_contact(db, user, "Ben")
    payload = {
        "from_contact_id": a.id,
        "to_contact_id": b.id,
        "relationship_type": "colleague",
        "shared_history": "some",
    }
    dispatch_tool_call("link_contacts", payload, user, db)

    # Re-record the same pair+type with a stronger history.
    payload["shared_history"] = "strong"
    result = dispatch_tool_call("link_contacts", payload, user, db)

    assert result["linked"]["created"] is False
    edges = _edges(db)
    assert len(edges) == 1  # no duplicate
    assert edges[0].shared_history == "strong"  # updated in place


def test_link_revives_soft_deleted_edge(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    a = _make_contact(db, user, "Ada")
    b = _make_contact(db, user, "Ben")
    edge = Relationship(
        from_contact_id=a.id, to_contact_id=b.id, relationship_type="board"
    )
    from datetime import datetime, timezone

    edge.deleted_at = datetime.now(timezone.utc)
    db.add(edge)
    db.commit()

    result = dispatch_tool_call(
        "link_contacts",
        {
            "from_contact_id": a.id,
            "to_contact_id": b.id,
            "relationship_type": "board",
            "shared_history": "some",
        },
        user,
        db,
    )

    assert result["linked"]["created"] is False
    edges = _edges(db)
    assert len(edges) == 1
    assert edges[0].deleted_at is None  # revived
    assert edges[0].shared_history == "some"


def test_link_requires_both_contacts_visible(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    other = user_factory()
    mine = _make_contact(db, user, "Mine")
    # A private contact owned by someone else is not visible to `user`.
    theirs = _make_contact(db, other, "Theirs", is_private=True)

    result = dispatch_tool_call(
        "link_contacts",
        {"from_contact_id": mine.id, "to_contact_id": theirs.id},
        user,
        db,
    )

    assert result["error"] == "not_found"
    assert _edges(db) == []


def test_link_unknown_contact_returns_not_found(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    a = _make_contact(db, user, "Ada")

    result = dispatch_tool_call(
        "link_contacts",
        {"from_contact_id": a.id, "to_contact_id": 999999},
        user,
        db,
    )
    assert result["error"] == "not_found"
    assert _edges(db) == []
