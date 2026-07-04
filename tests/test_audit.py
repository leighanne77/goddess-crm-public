"""Tests for the @audit_log decorator on write endpoints."""

from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Contact, User
from app.security import create_access_token


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _audit_rows_for(db: Session, user: User) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.id)
        )
    )


def test_create_contact_writes_audit_row(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    resp = client.post(
        "/api/contacts",
        headers=_auth_headers(user),
        json={"name": "Auditable Contact"},
    )
    assert resp.status_code == 201
    contact_id = resp.json()["id"]

    rows = _audit_rows_for(db, user)
    assert len(rows) == 1
    assert rows[0].action == "create_contact"
    assert rows[0].target_type == "contact"
    assert rows[0].target_id == contact_id
    assert rows[0].payload_hash is not None


def test_update_contact_writes_audit_row(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    contact = Contact(name="Original", owner_id=user.id)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    resp = client.patch(
        f"/api/contacts/{contact.id}",
        headers=_auth_headers(user),
        json={"name": "Renamed"},
    )
    assert resp.status_code == 200

    rows = _audit_rows_for(db, user)
    assert len(rows) == 1
    assert rows[0].action == "update_contact"
    assert rows[0].target_id == contact.id


def test_delete_contact_writes_audit_row(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    contact = Contact(name="Doomed", owner_id=user.id)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    resp = client.delete(f"/api/contacts/{contact.id}", headers=_auth_headers(user))
    assert resp.status_code == 204

    rows = _audit_rows_for(db, user)
    assert len(rows) == 1
    assert rows[0].action == "delete_contact"
    assert rows[0].target_id == contact.id
    assert rows[0].payload_hash is None


def test_share_contact_writes_audit_row(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    owner = user_factory(email="owner@test.fake")
    target = user_factory(email="target@test.fake")
    contact = Contact(name="Shared", owner_id=owner.id, is_private=True)
    db.add(contact)
    db.commit()
    db.refresh(contact)

    resp = client.post(
        f"/api/contacts/{contact.id}/share",
        headers=_auth_headers(owner),
        json={"user_id": target.id},
    )
    assert resp.status_code == 200

    rows = _audit_rows_for(db, owner)
    assert len(rows) == 1
    assert rows[0].action == "share_contact"
    assert rows[0].target_id == contact.id


def test_intro_seen_writes_audit_row(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(intro_seen=False)
    resp = client.patch("/api/users/me/intro-seen", headers=_auth_headers(user))
    assert resp.status_code == 204

    rows = _audit_rows_for(db, user)
    assert len(rows) == 1
    assert rows[0].action == "mark_intro_seen"
    assert rows[0].target_type == "user"
