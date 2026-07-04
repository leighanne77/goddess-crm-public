"""Privacy tests for contact endpoints.

Tests 1-6 cover the FM-10 (Privacy Violations) failure mode. Each
endpoint must return 404 (not 403) when a user tries to touch a
contact they cannot see — we don't reveal existence.
"""

from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Contact, User
from app.security import create_access_token


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _make_private_contact(db: Session, owner: User, name: str = "secret") -> Contact:
    contact = Contact(name=name, owner_id=owner.id, is_private=True)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def test_user_b_does_not_see_user_a_private_contact(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user_a = user_factory(email="alice@test.fake")
    user_b = user_factory(email="bob@test.fake")
    _make_private_contact(db, user_a)

    a_resp = client.get("/api/contacts", headers=_auth_headers(user_a))
    assert a_resp.status_code == 200
    assert len(a_resp.json()) == 1

    b_resp = client.get("/api/contacts", headers=_auth_headers(user_b))
    assert b_resp.status_code == 200
    assert b_resp.json() == []


def test_share_makes_private_contact_visible_to_target(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user_a = user_factory(email="alice@test.fake")
    user_b = user_factory(email="bob@test.fake")
    user_c = user_factory(email="carol@test.fake")
    contact = _make_private_contact(db, user_a)

    share_resp = client.post(
        f"/api/contacts/{contact.id}/share",
        headers=_auth_headers(user_a),
        json={"user_id": user_b.id},
    )
    assert share_resp.status_code == 200
    assert user_b.id in share_resp.json()["shared_with"]

    b_resp = client.get("/api/contacts", headers=_auth_headers(user_b))
    assert b_resp.status_code == 200
    assert len(b_resp.json()) == 1

    c_resp = client.get("/api/contacts", headers=_auth_headers(user_c))
    assert c_resp.status_code == 200
    assert c_resp.json() == []


def test_get_one_returns_404_when_contact_not_visible(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user_a = user_factory(email="alice@test.fake")
    user_b = user_factory(email="bob@test.fake")
    contact = _make_private_contact(db, user_a)

    resp = client.get(f"/api/contacts/{contact.id}", headers=_auth_headers(user_b))
    assert resp.status_code == 404


def test_patch_returns_404_when_contact_not_visible(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user_a = user_factory(email="alice@test.fake")
    user_b = user_factory(email="bob@test.fake")
    contact = _make_private_contact(db, user_a)

    resp = client.patch(
        f"/api/contacts/{contact.id}",
        headers=_auth_headers(user_b),
        json={"name": "hacked"},
    )
    assert resp.status_code == 404


def test_delete_returns_404_when_contact_not_visible(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    user_a = user_factory(email="alice@test.fake")
    user_b = user_factory(email="bob@test.fake")
    contact = _make_private_contact(db, user_a)

    resp = client.delete(f"/api/contacts/{contact.id}", headers=_auth_headers(user_b))
    assert resp.status_code == 404
