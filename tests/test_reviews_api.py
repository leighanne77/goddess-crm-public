"""Tests for the owner-facing review queue HTTP endpoints.

Auth model: owner of the target contact (NOT admin role). A user
sees only requests filed against contacts they own; resolving is
gated the same way.
"""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ChangeRequest, Contact, User
from app.security import create_access_token


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _make_contact(db: Session, owner: User, *, name: str = "Person") -> Contact:
    contact = Contact(
        name=name,
        primary_fund="General",
        contact_type="Other",
        owner_id=owner.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _make_request(
    db: Session,
    *,
    requester: User,
    contact: Contact,
    kind: str = "off_fly_list",
    payload: dict | None = None,
    status: str = "pending",
) -> ChangeRequest:
    cr = ChangeRequest(
        requester_id=requester.id,
        contact_id=contact.id,
        kind=kind,
        payload=payload,
        status=status,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr


# ---------------------------------------------------------------------------
# GET /admin/reviews
# ---------------------------------------------------------------------------


def test_unauthenticated_gets_401(client: TestClient) -> None:
    resp = client.get("/api/admin/reviews")
    assert resp.status_code == 401


def test_owner_sees_only_requests_against_own_contacts(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    alice = user_factory(email="alice@test.fake")
    bob = user_factory(email="bob@test.fake")
    requester = user_factory(email="req@test.fake")

    alice_contact = _make_contact(db, alice, name="A")
    bob_contact = _make_contact(db, bob, name="B")
    _make_request(db, requester=requester, contact=alice_contact)
    _make_request(db, requester=requester, contact=bob_contact)

    resp = client.get("/api/admin/reviews", headers=_bearer(alice))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    row = body["rows"][0]
    assert row["contact_name"] == "A"
    assert row["requester_email"] == "req@test.fake"


def test_default_filter_is_pending(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    _make_request(db, requester=requester, contact=contact, status="pending")
    _make_request(db, requester=requester, contact=contact, status="approved")
    _make_request(db, requester=requester, contact=contact, status="disapproved")

    resp = client.get("/api/admin/reviews", headers=_bearer(owner))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["rows"][0]["status"] == "pending"


def test_status_all_returns_every_row(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    _make_request(db, requester=requester, contact=contact, status="pending")
    _make_request(db, requester=requester, contact=contact, status="approved")

    resp = client.get("/api/admin/reviews?status=all", headers=_bearer(owner))
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_kind_filter(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    _make_request(db, requester=requester, contact=contact, kind="off_fly_list")
    _make_request(
        db,
        requester=requester,
        contact=contact,
        kind="patina_override",
        payload={"kind": "patina_override", "items": []},
    )

    resp = client.get("/api/admin/reviews?kind=off_fly_list", headers=_bearer(owner))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["rows"][0]["kind"] == "off_fly_list"


def test_pagination_caps_page_size(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    for _ in range(5):
        _make_request(db, requester=requester, contact=contact)

    resp = client.get("/api/admin/reviews?page_size=2", headers=_bearer(owner))
    assert resp.status_code == 200
    body = resp.json()
    assert body["page_size"] == 2
    assert len(body["rows"]) == 2
    assert body["total"] == 5


# ---------------------------------------------------------------------------
# POST /admin/reviews/{id}/resolve
# ---------------------------------------------------------------------------


def test_owner_can_approve_off_fly_list(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    contact.fly_status = "Active"
    db.commit()
    cr = _make_request(db, requester=requester, contact=contact)

    resp = client.post(
        f"/api/admin/reviews/{cr.id}/resolve",
        headers=_bearer(owner),
        json={"decision": "approve", "note": "ok"},
    )
    assert resp.status_code == 200
    row = resp.json()
    assert row["status"] == "approved"
    assert row["resolved_by_id"] == owner.id
    assert row["resolution_note"] == "ok"
    db.refresh(contact)
    assert contact.fly_status == "Off Fly List"


def test_owner_can_disapprove_leaves_contact_untouched(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    contact.fly_status = "Active"
    db.commit()
    cr = _make_request(db, requester=requester, contact=contact)

    resp = client.post(
        f"/api/admin/reviews/{cr.id}/resolve",
        headers=_bearer(owner),
        json={"decision": "disapprove"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disapproved"
    db.refresh(contact)
    assert contact.fly_status == "Active"


def test_non_owner_gets_403(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    intruder = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    cr = _make_request(db, requester=requester, contact=contact)

    resp = client.post(
        f"/api/admin/reviews/{cr.id}/resolve",
        headers=_bearer(intruder),
        json={"decision": "approve"},
    )
    assert resp.status_code == 403


def test_resolve_already_resolved_returns_409(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    requester = user_factory()
    contact = _make_contact(db, owner)
    cr = _make_request(db, requester=requester, contact=contact, status="approved")

    resp = client.post(
        f"/api/admin/reviews/{cr.id}/resolve",
        headers=_bearer(owner),
        json={"decision": "approve"},
    )
    assert resp.status_code == 409


def test_resolve_nonexistent_returns_404(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    resp = client.post(
        "/api/admin/reviews/99999/resolve",
        headers=_bearer(owner),
        json={"decision": "approve"},
    )
    assert resp.status_code == 404
