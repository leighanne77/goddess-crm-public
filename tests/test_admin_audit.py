"""Tests for the admin audit-log endpoints.

Privacy-critical: member-role users get a flat 403 on every admin
endpoint. Admins get the full audit trail across the team.
"""

from datetime import datetime, timezone
from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.security import create_access_token


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _make_audit(db: Session, user: User, *, action: str = "create_contact") -> AuditLog:
    row = AuditLog(
        user_id=user.id,
        action=action,
        target_type="contact",
        target_id=1,
        payload_hash="abc123",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def test_member_gets_403_on_audit_list(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    member = user_factory(role="member")
    resp = client.get("/api/admin/audit", headers=_bearer(member))
    assert resp.status_code == 403


def test_member_gets_403_on_audit_csv(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    member = user_factory(role="member")
    resp = client.get("/api/admin/audit.csv", headers=_bearer(member))
    assert resp.status_code == 403


def test_unauthenticated_gets_401(client: TestClient, db: Session) -> None:
    resp = client.get("/api/admin/audit")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Listing + pagination
# ---------------------------------------------------------------------------


def test_admin_can_list_audit_rows(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    member = user_factory(role="member", email="m@test.fake")
    _make_audit(db, admin, action="create_contact")
    _make_audit(db, member, action="update_contact")

    resp = client.get("/api/admin/audit", headers=_bearer(admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 50
    # Newest-first ordering
    assert body["rows"][0]["action"] == "update_contact"
    # Email is joined in
    assert body["rows"][1]["user_email"] == admin.email


def test_pagination_respects_page_and_page_size(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    for i in range(7):
        _make_audit(db, admin, action=f"action_{i}")

    resp = client.get("/api/admin/audit?page=2&page_size=3", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 7
    assert len(body["rows"]) == 3
    assert body["page"] == 2
    # Newest-first; page 2 of 3 should be rows 3 and 4 from the seed
    # (actions counted from 0).
    assert body["rows"][0]["action"] == "action_3"


def test_filter_by_action(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    _make_audit(db, admin, action="create_contact")
    _make_audit(db, admin, action="export_sheet")
    _make_audit(db, admin, action="export_sheet")

    resp = client.get("/api/admin/audit?action=export_sheet", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(r["action"] == "export_sheet" for r in body["rows"])


def test_filter_by_user_id(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    other = user_factory(role="admin", email="other@test.fake")
    _make_audit(db, admin)
    _make_audit(db, other)
    _make_audit(db, other)

    resp = client.get(f"/api/admin/audit?user_id={other.id}", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(r["user_id"] == other.id for r in body["rows"])


def test_page_size_capped_at_200(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    resp = client.get("/api/admin/audit?page_size=500", headers=_bearer(admin))
    # Pydantic Query(le=200) returns 422 on over-limit
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# CSV download
# ---------------------------------------------------------------------------


def test_admin_csv_download_contains_all_rows(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    _make_audit(db, admin, action="create_contact")
    _make_audit(db, admin, action="update_contact")
    _make_audit(db, admin, action="export_sheet")

    resp = client.get("/api/admin/audit.csv", headers=_bearer(admin))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"].lower()
    body = resp.text
    # Header row
    assert "id,user_id,user_email,action" in body.splitlines()[0]
    # All three actions present
    for action in ["create_contact", "update_contact", "export_sheet"]:
        assert action in body


def test_csv_respects_action_filter(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    _make_audit(db, admin, action="create_contact")
    _make_audit(db, admin, action="export_sheet")

    resp = client.get(
        "/api/admin/audit.csv?action=export_sheet", headers=_bearer(admin)
    )
    assert resp.status_code == 200
    assert "export_sheet" in resp.text
    assert "create_contact" not in resp.text


def test_csv_filename_includes_today(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(role="admin")
    _make_audit(db, admin)
    resp = client.get("/api/admin/audit.csv", headers=_bearer(admin))
    assert resp.status_code == 200
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert today in resp.headers["content-disposition"]
