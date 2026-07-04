"""Tests for the /export/sheets endpoint.

The Sheets service is mocked — we never hit Google. The test verifies
the wiring: privacy filter applied, headers + rows formatted correctly,
errors translated to the right HTTP status, and audit log written.
"""

from typing import Callable
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Contact, User
from app.security import create_access_token
from app.services.sheets import (
    CreatedSheet,
    SheetsExportError,
    SheetsQuotaError,
    SheetsScopeError,
)


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _make_contact(
    db: Session,
    owner: User,
    *,
    name: str = "Person",
    is_private: bool = False,
    primary_fund: str = "General",
    contact_type: str = "Other",
) -> Contact:
    contact = Contact(
        name=name,
        primary_fund=primary_fund,
        contact_type=contact_type,
        is_private=is_private,
        owner_id=owner.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _patch_sheets_create(return_value=None):
    """Helper to patch the sheets.create_sheet at the import site."""
    if return_value is None:
        return_value = CreatedSheet(
            id="sheet-xyz",
            url="https://docs.google.com/spreadsheets/d/sheet-xyz",
        )
    return patch(
        "app.routers.exports.sheets_service.create_sheet",
        return_value=return_value,
    )


def test_export_happy_path_returns_sheet_url(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(google_access_token="fake-token")
    _make_contact(db, user, name="Marcus", primary_fund="Maritime")

    with _patch_sheets_create() as mock_create:
        resp = client.post(
            "/api/export/sheets",
            json={"primary_fund": "Maritime"},
            headers=_bearer(user),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sheet_url"].endswith("sheet-xyz")
    assert body["contact_count"] == 1
    # The Sheets service was called with the right shape.
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["access_token"] == "fake-token"
    assert "Name" in call_kwargs["headers"]
    assert call_kwargs["rows"][0][0] == "Marcus"


def test_export_respects_privacy_filter(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Bob exporting must NOT see Alice's private contacts."""
    alice = user_factory(email="alice@test.fake", google_access_token="t1")
    bob = user_factory(email="bob@test.fake", google_access_token="t2")
    _make_contact(db, alice, name="Private Alice", is_private=True)
    _make_contact(db, alice, name="Public Alice", is_private=False)

    with _patch_sheets_create() as mock_create:
        resp = client.post("/api/export/sheets", json={}, headers=_bearer(bob))

    assert resp.status_code == 200, resp.text
    rows = mock_create.call_args.kwargs["rows"]
    names_in_export = [r[0] for r in rows]
    assert "Public Alice" in names_in_export
    assert "Private Alice" not in names_in_export


def test_export_returns_404_when_no_contacts_match(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(google_access_token="t")
    # Seed a contact that WON'T match the filter.
    _make_contact(db, user, name="Marcus", primary_fund="Maritime")

    resp = client.post(
        "/api/export/sheets",
        json={"primary_fund": "Energy"},
        headers=_bearer(user),
    )
    assert resp.status_code == 404


def test_export_412_when_user_missing_google_token(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Pre-Day-5 sessions don't have the Google token captured."""
    user = user_factory(google_access_token=None)
    _make_contact(db, user, name="Marcus")

    resp = client.post("/api/export/sheets", json={}, headers=_bearer(user))
    assert resp.status_code == 412
    assert "log out" in resp.json()["detail"].lower()


def test_export_falls_back_to_csv_when_sheets_scope_missing(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Slice 3: SheetsScopeError now triggers automatic CSV fallback —
    the user gets a downloadable file instead of a hard 403."""
    user = user_factory(google_access_token="t")
    _make_contact(db, user, name="Marcus", primary_fund="Maritime")

    with patch(
        "app.routers.exports.sheets_service.create_sheet",
        side_effect=SheetsScopeError("no scope"),
    ):
        resp = client.post(
            "/api/export/sheets",
            json={"primary_fund": "Maritime"},
            headers=_bearer(user),
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"].lower()
    assert ".csv" in resp.headers["content-disposition"].lower()
    assert "Marcus" in resp.text
    assert "Name" in resp.text  # header row


def test_export_429_when_sheets_quota_exceeded(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(google_access_token="t")
    _make_contact(db, user, name="Marcus")

    with patch(
        "app.routers.exports.sheets_service.create_sheet",
        side_effect=SheetsQuotaError("rate limited"),
    ):
        resp = client.post("/api/export/sheets", json={}, headers=_bearer(user))

    assert resp.status_code == 429


def test_export_502_for_other_sheets_failures(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(google_access_token="t")
    _make_contact(db, user, name="Marcus")

    with patch(
        "app.routers.exports.sheets_service.create_sheet",
        side_effect=SheetsExportError("internal"),
    ):
        resp = client.post("/api/export/sheets", json={}, headers=_bearer(user))

    assert resp.status_code == 502


def test_export_requires_authentication(client: TestClient, db: Session) -> None:
    """No auth header → 401."""
    resp = client.post("/api/export/sheets", json={})
    assert resp.status_code == 401


def test_csv_export_returns_csv_attachment(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Direct /export/csv — never touches Google, always streams CSV."""
    user = user_factory()
    _make_contact(db, user, name="Marcus", primary_fund="Maritime")
    _make_contact(db, user, name="Diana", primary_fund="Critical Minerals")

    resp = client.post(
        "/api/export/csv",
        json={"primary_fund": "Maritime"},
        headers=_bearer(user),
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"].lower()
    body = resp.text
    assert "Name" in body  # header row
    assert "Marcus" in body
    assert "Diana" not in body  # filtered out


def test_csv_export_respects_privacy_filter(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Bob's CSV export must NOT include Alice's privates."""
    alice = user_factory(email="alice@test.fake")
    bob = user_factory(email="bob@test.fake")
    _make_contact(db, alice, name="Private Alice", is_private=True)
    _make_contact(db, alice, name="Public Alice", is_private=False)

    resp = client.post("/api/export/csv", json={}, headers=_bearer(bob))
    assert resp.status_code == 200
    assert "Public Alice" in resp.text
    assert "Private Alice" not in resp.text


def test_csv_export_404_when_no_contacts_match(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    _make_contact(db, user, name="Marcus", primary_fund="Maritime")
    resp = client.post(
        "/api/export/csv",
        json={"primary_fund": "Energy"},
        headers=_bearer(user),
    )
    assert resp.status_code == 404


def test_csv_export_does_not_require_google_token(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """No google_access_token needed — CSV is local."""
    user = user_factory(google_access_token=None)
    _make_contact(db, user, name="Marcus")

    resp = client.post("/api/export/csv", json={}, headers=_bearer(user))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


def test_csv_export_writes_audit_log_row(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    _make_contact(db, user, name="Marcus")

    from app.models import AuditLog

    before = db.query(AuditLog).count()
    resp = client.post("/api/export/csv", json={}, headers=_bearer(user))
    assert resp.status_code == 200
    after = db.query(AuditLog).count()
    assert after == before + 1
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    assert last is not None
    assert last.action == "export_csv"
    assert last.user_id == user.id


def test_export_writes_audit_log_row(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(google_access_token="t")
    _make_contact(db, user, name="Marcus")

    from app.models import AuditLog

    before = db.query(AuditLog).count()

    with _patch_sheets_create():
        resp = client.post(
            "/api/export/sheets",
            json={"primary_fund": "General"},
            headers=_bearer(user),
        )
    assert resp.status_code == 200

    after = db.query(AuditLog).count()
    assert after == before + 1
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    assert last is not None
    assert last.action == "export_sheet"
    assert last.user_id == user.id
