"""Phase 5 Slice 1 — schema tests for the warm-introduction engine.

Covers the two new pieces:
  - contacts.opt_in_status (default PENDING, settable, validated)
  - the relationships edge table (defaults + the self-edge and
    duplicate-pair constraints)

The engine/pathfinding itself is later slices; this just proves the
foundation holds.
"""

from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Contact, Relationship, User
from app.security import create_access_token


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _make_contact(db: Session, owner: User, name: str) -> Contact:
    contact = Contact(name=name, owner_id=owner.id)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


# ---------------------------------------------------------------------------
# opt_in_status
# ---------------------------------------------------------------------------


def test_new_contact_defaults_to_pending(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    resp = client.post(
        "/api/contacts", headers=_auth_headers(user), json={"name": "No Optin Given"}
    )
    assert resp.status_code == 201
    # Nobody is offered as an intro path until explicitly approved.
    assert resp.json()["opt_in_status"] == "PENDING"


def test_create_contact_with_approved_opt_in(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    resp = client.post(
        "/api/contacts",
        headers=_auth_headers(user),
        json={"name": "Cleared Contact", "opt_in_status": "APPROVED"},
    )
    assert resp.status_code == 201
    assert resp.json()["opt_in_status"] == "APPROVED"


def test_patch_opt_in_status_roundtrips_for_owner(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    contact_id = client.post(
        "/api/contacts", headers=_auth_headers(user), json={"name": "Approve Me"}
    ).json()["id"]

    resp = client.patch(
        f"/api/contacts/{contact_id}",
        headers=_auth_headers(user),
        json={"opt_in_status": "APPROVED"},
    )
    assert resp.status_code == 200
    assert resp.json()["opt_in_status"] == "APPROVED"


def test_invalid_opt_in_status_rejected(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    resp = client.post(
        "/api/contacts",
        headers=_auth_headers(user),
        json={"name": "Bad Optin", "opt_in_status": "MAYBE"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# relationships (edges)
# ---------------------------------------------------------------------------


def test_relationship_insert_and_defaults(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    a = _make_contact(db, owner, "Intermediary A")
    b = _make_contact(db, owner, "Target B")

    edge = Relationship(from_contact_id=a.id, to_contact_id=b.id)
    db.add(edge)
    db.commit()
    db.refresh(edge)

    assert edge.relationship_type == "Unknown"
    assert edge.shared_history == "none"
    assert edge.source == "manual"
    assert edge.confidence == 1.0
    assert edge.deleted_at is None


def test_relationship_self_edge_rejected(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    a = _make_contact(db, owner, "Lonely A")

    db.add(Relationship(from_contact_id=a.id, to_contact_id=a.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_relationship_duplicate_pair_type_rejected(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    a = _make_contact(db, owner, "A")
    b = _make_contact(db, owner, "B")

    db.add(
        Relationship(
            from_contact_id=a.id, to_contact_id=b.id, relationship_type="colleague"
        )
    )
    db.commit()

    # Same (from, to, type) → unique-constraint violation.
    db.add(
        Relationship(
            from_contact_id=a.id, to_contact_id=b.id, relationship_type="colleague"
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # A different type for the same pair is allowed.
    db.add(
        Relationship(
            from_contact_id=a.id, to_contact_id=b.id, relationship_type="board"
        )
    )
    db.commit()
