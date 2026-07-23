"""Non-privacy CRUD tests for the contacts router."""

from typing import Any, Callable

from fastapi.testclient import TestClient

from app.models import User
from app.security import create_access_token


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def test_post_then_patch_bumps_updated_at(
    client: TestClient,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()

    create_resp = client.post(
        "/api/contacts",
        headers=_auth_headers(user),
        json={"name": "Initial Name"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    contact_id = created["id"]
    created_at = created["created_at"]
    assert created["updated_at"] == created_at

    patch_resp = client.patch(
        f"/api/contacts/{contact_id}",
        headers=_auth_headers(user),
        json={"name": "Renamed"},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["name"] == "Renamed"
    assert patched["updated_at"] > created_at


def test_delete_soft_deletes_so_contact_no_longer_listed(
    client: TestClient,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()

    create_resp = client.post(
        "/api/contacts",
        headers=_auth_headers(user),
        json={"name": "To Be Deleted"},
    )
    contact_id = create_resp.json()["id"]

    delete_resp = client.delete(
        f"/api/contacts/{contact_id}", headers=_auth_headers(user)
    )
    assert delete_resp.status_code == 204

    list_resp = client.get("/api/contacts", headers=_auth_headers(user))
    assert list_resp.status_code == 200
    assert all(c["id"] != contact_id for c in list_resp.json())

    # Direct fetch also hides it (404, not 410 — soft delete is invisible).
    get_resp = client.get(f"/api/contacts/{contact_id}", headers=_auth_headers(user))
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 2 Slice 6.8 — changelog endpoint
# ---------------------------------------------------------------------------


def test_changelog_returns_actions_newest_first(
    client: TestClient, user_factory: Callable[..., User]
) -> None:
    user = user_factory()
    # Create + update generate two audit rows.
    create_resp = client.post(
        "/api/contacts",
        headers=_auth_headers(user),
        json={"name": "Marcus", "fly_status": "Must Fly"},
    )
    assert create_resp.status_code == 201
    contact_id = create_resp.json()["id"]
    client.patch(
        f"/api/contacts/{contact_id}",
        headers=_auth_headers(user),
        json={"title": "Managing Partner"},
    )

    resp = client.get(
        f"/api/contacts/{contact_id}/changelog", headers=_auth_headers(user)
    )
    assert resp.status_code == 200
    entries = resp.json()
    # Newest first — update comes before create.
    actions = [e["action"] for e in entries]
    assert actions[0] == "update_contact"
    assert actions[-1] == "create_contact"
    # Friendly labels populated.
    assert any(e["action_label"] == "updated the contact" for e in entries)
    assert any(e["action_label"] == "created the contact" for e in entries)
    # Actor name passed through.
    assert all(e["actor_name"] == user.name for e in entries)


def test_changelog_404_for_hidden_private_contact(
    client: TestClient, db, user_factory: Callable[..., User]
) -> None:
    """A non-owner who can't even see the contact (owner disabled
    existence hints) gets 404 — not 403, don't leak existence."""
    from app.models import Contact

    owner = user_factory(email="alice@test.fake")
    owner.allow_existence_hints = False
    db.commit()
    bob = user_factory(email="bob@test.fake")
    contact = Contact(
        name="Secret",
        owner_id=owner.id,
        is_private=True,
        primary_fund="Maritime",
        fly_status="Must Fly",
    )
    db.add(contact)
    db.commit()

    resp = client.get(
        f"/api/contacts/{contact.id}/changelog", headers=_auth_headers(bob)
    )
    assert resp.status_code == 404


def test_changelog_excludes_redacted_reveal_audit_rows(
    client: TestClient, db, user_factory: Callable[..., User]
) -> None:
    """redacted_reveal is a READ, not a CHANGE. Must NOT appear in the
    contact's change history — otherwise every search inflates the log."""
    from app.models import AuditLog, Contact

    owner = user_factory(email="alice@test.fake")
    contact = Contact(
        name="Marcus",
        owner_id=owner.id,
        is_private=False,
        primary_fund="Maritime",
        fly_status="Must Fly",
    )
    db.add(contact)
    db.commit()

    # Synthesize a redacted_reveal audit row + a real update row.
    db.add(
        AuditLog(
            user_id=owner.id,
            action="redacted_reveal",
            target_type="contact",
            target_id=contact.id,
        )
    )
    db.add(
        AuditLog(
            user_id=owner.id,
            action="update_contact",
            target_type="contact",
            target_id=contact.id,
        )
    )
    db.commit()

    resp = client.get(
        f"/api/contacts/{contact.id}/changelog", headers=_auth_headers(owner)
    )
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert "redacted_reveal" not in actions
    assert "update_contact" in actions


def test_changelog_redacted_viewer_sees_history(
    client: TestClient, db, user_factory: Callable[..., User]
) -> None:
    """A teammate who only sees the contact in redacted form can still
    pull its changelog — the audit metadata is no more sensitive than
    the redacted card itself, and helps explain 'why does Jordan Blake
    have a contact at ADIA' (e.g. 'transferred from Sam Chen on May 1')."""
    from app.models import Contact

    owner = user_factory(email="alice@test.fake")
    bob = user_factory(email="bob@test.fake")
    contact = Contact(
        name="Secret",
        owner_id=owner.id,
        is_private=True,
        primary_fund="Maritime",
        fly_status="Must Fly",
    )
    db.add(contact)
    db.commit()

    resp = client.get(
        f"/api/contacts/{contact.id}/changelog", headers=_auth_headers(bob)
    )
    assert resp.status_code == 200  # NOT 404 — redactable means visible-enough


def test_search_results_include_notes_for_owner(
    client: TestClient, db, user_factory: Callable[..., User]
) -> None:
    """Slice 6.8 — `notes` is back in tool results for fully-visible
    rows so the expanded card view + chat readback can use it."""
    from app.models import Contact
    from app.services.tool_dispatch import dispatch_tool_call

    owner = user_factory()
    contact = Contact(
        name="Marcus",
        owner_id=owner.id,
        notes="Focus on defense shipyards.",
        primary_fund="Maritime",
        fly_status="Must Fly",
    )
    db.add(contact)
    db.commit()

    result = dispatch_tool_call("search_contacts", {}, owner, db)
    assert result["results"][0]["notes"] == "Focus on defense shipyards."


def test_search_results_omit_notes_on_redacted_rows(
    db, user_factory: Callable[..., User]
) -> None:
    """Redacted rows MUST never carry notes — notes is on the never-
    reveal PII list. Regression pin for the Slice 6.5 security gate."""
    from app.models import Contact
    from app.services.tool_dispatch import dispatch_tool_call

    owner = user_factory(email="alice@test.fake")
    bob = user_factory(email="bob@test.fake")
    contact = Contact(
        name="Secret",
        owner_id=owner.id,
        is_private=True,
        notes="must not leak",
        primary_fund="Energy",
        fly_status="Must Fly",
    )
    db.add(contact)
    db.commit()

    result = dispatch_tool_call("search_contacts", {}, bob, db)
    redacted = next(r for r in result["results"] if r["is_redacted"])
    assert "notes" not in redacted or redacted.get("notes") in (None, "")


# ---------------------------------------------------------------------------
# Phase 2 Slice 6.9 — field-level diffs in the change log
# ---------------------------------------------------------------------------


def test_changelog_update_carries_field_diff(
    client: TestClient, db, user_factory: Callable[..., User]
) -> None:
    """Owner sees update_contact entries with a per-field changes list.

    Goes through the dispatch_tool_call path (chat surface) because
    that's where Slice 6.9 added the metadata. The REST PATCH endpoint
    still uses the @audit_log decorator that doesn't yet populate
    payload_metadata — a known gap; chat is the primary write surface."""
    from app.services.tool_dispatch import dispatch_tool_call

    user = user_factory()
    created = dispatch_tool_call(
        "create_contact",
        {
            "name": "Marcus",
            "fly_status": "Fly List",
            "is_private": False,
            "title": "Associate",
        },
        user,
        db,
    )
    contact_id = created["created"]["id"]
    dispatch_tool_call(
        "update_contact",
        {
            "contact_id": contact_id,
            "fly_status": "Must Fly",
            "title": "Managing Partner",
        },
        user,
        db,
    )

    resp = client.get(
        f"/api/contacts/{contact_id}/changelog", headers=_auth_headers(user)
    )
    assert resp.status_code == 200
    update_entry = next(e for e in resp.json() if e["action"] == "update_contact")
    changes = update_entry["metadata"]["changes"]
    by_field = {c["field"]: c for c in changes}
    assert by_field["fly_status"]["old"] == "Fly List"
    assert by_field["fly_status"]["new"] == "Must Fly"
    assert by_field["title"]["old"] == "Associate"
    assert by_field["title"]["new"] == "Managing Partner"


def test_changelog_redacted_caller_only_sees_revealed_field_diffs(
    db, user_factory: Callable[..., User]
) -> None:
    """Non-owner redacted caller MUST NOT see before/after values for
    fields that aren't in reveal_fields. Use dispatch directly to
    populate the metadata, then call the endpoint as the redacted user."""
    from app.models import AuditLog, Contact

    owner = user_factory(email="alice@test.fake")
    bob = user_factory(email="bob@test.fake")
    contact = Contact(
        name="Marcus",
        owner_id=owner.id,
        is_private=True,
        primary_fund="Maritime",
        fly_status="Fly List",
        # Default reveal_fields gets applied via server_default at INSERT.
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)

    # Synthesize an update_contact audit row whose payload_metadata
    # contains diff entries for BOTH a revealed field (primary_fund)
    # and a hidden one (notes — which is PII and never reveal-able).
    db.add(
        AuditLog(
            user_id=owner.id,
            action="update_contact",
            target_type="contact",
            target_id=contact.id,
            payload_metadata={
                "changes": [
                    {"field": "primary_fund", "old": "Maritime", "new": "Energy"},
                    {"field": "notes", "old": "old secret", "new": "new secret"},
                ]
            },
        )
    )
    db.commit()

    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.security import create_access_token

    def _override() -> Any:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/api/contacts/{contact.id}/changelog",
                headers={
                    "Authorization": f"Bearer {create_access_token(user_id=bob.id)}"
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    entry = next(e for e in resp.json() if e["action"] == "update_contact")
    fields = [c["field"] for c in entry["metadata"]["changes"]]
    # primary_fund is in the default reveal set -> visible.
    assert "primary_fund" in fields
    # notes is on the never-reveal PII list -> stripped server-side.
    assert "notes" not in fields
    # And the secret values must not appear anywhere in the response body.
    assert "old secret" not in resp.text
    assert "new secret" not in resp.text


def test_changelog_transfer_metadata_includes_old_and_new_owner(
    db, user_factory: Callable[..., User]
) -> None:
    from app.models import Contact
    from app.services.tool_dispatch import dispatch_tool_call

    leigh_anne = user_factory(email="alice@test.fake", name="Alex Rivera")
    heather_jo = user_factory(email="bob@test.fake", name="Jordan Blake")
    contact = Contact(
        name="Marcus",
        owner_id=leigh_anne.id,
        primary_fund="Maritime",
        fly_status="Must Fly",
        is_private=False,
    )
    db.add(contact)
    db.commit()

    _first = dispatch_tool_call(
        "transfer_contact",
        {"contact_id": contact.id, "new_owner_email": heather_jo.email},
        leigh_anne,
        db,
    )
    assert _first["error"] == "confirm_required"
    dispatch_tool_call(
        "transfer_contact",
        {
            "contact_id": contact.id,
            "new_owner_email": heather_jo.email,
            "confirm_token": _first["confirm_token"],
        },
        leigh_anne,
        db,
    )

    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.security import create_access_token

    def _override() -> Any:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/api/contacts/{contact.id}/changelog",
                headers={
                    "Authorization": (
                        f"Bearer {create_access_token(user_id=heather_jo.id)}"
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    entry = next(e for e in resp.json() if e["action"] == "transfer_contact")
    assert entry["metadata"]["old_owner_name"] == "Alex Rivera"
    assert entry["metadata"]["new_owner_name"] == "Jordan Blake"


def test_changelog_picks_up_change_request_filed_against_contact(
    db, user_factory: Callable[..., User]
) -> None:
    """request_change rows target the change_request itself, but the
    changelog endpoint joins through ChangeRequest.contact_id so they
    appear in the contact's history."""
    from app.models import Contact
    from app.services.tool_dispatch import dispatch_tool_call

    owner = user_factory(email="alice@test.fake")
    other = user_factory(email="bob@test.fake")
    contact = Contact(
        name="Marcus",
        owner_id=owner.id,
        primary_fund="Maritime",
        fly_status="Fly List",
        is_private=False,
    )
    db.add(contact)
    db.commit()

    dispatch_tool_call(
        "request_change",
        {"contact_id": contact.id, "payload": {"kind": "off_fly_list"}},
        other,
        db,
    )

    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.security import create_access_token

    def _override() -> Any:
        yield db

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as client:
            resp = client.get(
                f"/api/contacts/{contact.id}/changelog",
                headers={
                    "Authorization": f"Bearer {create_access_token(user_id=owner.id)}"
                },
            )
    finally:
        app.dependency_overrides.clear()

    actions = [e["action"] for e in resp.json()]
    assert "request_change" in actions
    rc_entry = next(e for e in resp.json() if e["action"] == "request_change")
    assert rc_entry["metadata"]["kind"] == "off_fly_list"
