"""Tests for the Phase 2 review queue: request_change + resolve_change_request.

These tools let a non-owner ask the owner to either take a contact off
the fly list or replace their patina marks. The handlers enforce:
  - request_change: requester != owner, contact must be visible
  - resolve_change_request: only the owner can resolve, not idempotent
"""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.models import ChangeRequest, Contact, User
from app.services.tool_dispatch import ToolDispatchError, dispatch_tool_call


def _make_contact(
    db: Session, owner: User, *, name: str = "Person", is_private: bool = False
) -> Contact:
    contact = Contact(
        name=name,
        primary_fund="General",
        contact_type="Other",
        is_private=is_private,
        owner_id=owner.id,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


# ---------------------------------------------------------------------------
# request_change
# ---------------------------------------------------------------------------


def test_request_change_off_fly_list_creates_pending(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    contact = _make_contact(db, owner, name="Marcus")

    result = dispatch_tool_call(
        "request_change",
        {
            "contact_id": contact.id,
            "payload": {"kind": "off_fly_list"},
            "reason": "He's leaving the firm.",
        },
        requester,
        db,
    )
    assert result["status"] == "pending"
    assert result["kind"] == "off_fly_list"
    assert result["owner_id"] == owner.id

    cr = db.get(ChangeRequest, result["request_id"])
    assert cr is not None
    assert cr.requester_id == requester.id
    assert cr.contact_id == contact.id
    # off_fly_list has no payload body — only the kind itself.
    assert cr.payload is None
    assert cr.reason == "He's leaving the firm."


def test_request_change_patina_override_stores_items(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    contact = _make_contact(db, owner, name="Marcus")

    result = dispatch_tool_call(
        "request_change",
        {
            "contact_id": contact.id,
            "payload": {
                "kind": "patina_override",
                "items": [
                    {"kind": "sticker", "shape": "smiley"},
                    {"kind": "pencilNote", "text": "say hi"},
                ],
            },
        },
        requester,
        db,
    )
    cr = db.get(ChangeRequest, result["request_id"])
    assert cr is not None
    assert cr.payload is not None
    assert cr.payload["kind"] == "patina_override"
    assert len(cr.payload["items"]) == 2


def test_request_change_rejected_when_owner_files(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    contact = _make_contact(db, owner)

    result = dispatch_tool_call(
        "request_change",
        {"contact_id": contact.id, "payload": {"kind": "off_fly_list"}},
        owner,
        db,
    )
    assert result["error"] == "owner_should_edit_directly"
    # No row created.
    assert db.query(ChangeRequest).count() == 0


def test_request_change_not_visible_returns_not_found(
    db: Session, user_factory: Callable[..., User]
) -> None:
    """Requester can't even see the contact (private + not owner)."""
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    private = _make_contact(db, owner, is_private=True)

    result = dispatch_tool_call(
        "request_change",
        {"contact_id": private.id, "payload": {"kind": "off_fly_list"}},
        requester,
        db,
    )
    assert result["error"] == "not_found"
    assert db.query(ChangeRequest).count() == 0


def test_request_change_unknown_contact_returns_not_found(
    db: Session, user_factory: Callable[..., User]
) -> None:
    requester = user_factory()
    result = dispatch_tool_call(
        "request_change",
        {"contact_id": 99999, "payload": {"kind": "off_fly_list"}},
        requester,
        db,
    )
    assert result["error"] == "not_found"


def test_request_change_malformed_payload_raises(
    db: Session, user_factory: Callable[..., User]
) -> None:
    """Discriminated union must reject unknown kinds at validation time."""
    requester = user_factory()
    with pytest.raises(ToolDispatchError, match="Invalid params"):
        dispatch_tool_call(
            "request_change",
            {"contact_id": 1, "payload": {"kind": "delete_user"}},
            requester,
            db,
        )


# ---------------------------------------------------------------------------
# resolve_change_request
# ---------------------------------------------------------------------------


def _file_off_fly_list(
    db: Session, owner: User, requester: User
) -> tuple[Contact, int]:
    contact = _make_contact(db, owner, name="Marcus")
    result = dispatch_tool_call(
        "request_change",
        {"contact_id": contact.id, "payload": {"kind": "off_fly_list"}},
        requester,
        db,
    )
    return contact, result["request_id"]


def test_resolve_approve_off_fly_list_applies_change(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    contact, request_id = _file_off_fly_list(db, owner, requester)
    assert contact.fly_status != "Off Fly List"

    result = dispatch_tool_call(
        "resolve_change_request",
        {"request_id": request_id, "decision": "approve", "note": "agreed"},
        owner,
        db,
    )
    assert result["status"] == "approved"
    assert result["applied"] is True

    db.refresh(contact)
    assert contact.fly_status == "Off Fly List"

    cr = db.get(ChangeRequest, request_id)
    assert cr is not None
    assert cr.resolved_by_id == owner.id
    assert cr.resolution_note == "agreed"
    assert cr.resolved_at is not None


def test_resolve_disapprove_leaves_contact_untouched(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    contact, request_id = _file_off_fly_list(db, owner, requester)
    original_status = contact.fly_status

    result = dispatch_tool_call(
        "resolve_change_request",
        {"request_id": request_id, "decision": "disapprove"},
        owner,
        db,
    )
    assert result["status"] == "disapproved"
    assert result["applied"] is False

    db.refresh(contact)
    assert contact.fly_status == original_status


def test_resolve_approve_patina_override_replaces_list(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    contact = _make_contact(db, owner, name="Marcus")
    contact.patina_overrides = [{"kind": "sticker", "shape": "star"}]
    db.commit()

    new_items = [
        {"kind": "pencilNote", "text": "Ghostbusters"},
        {"kind": "doodle", "shape": "smiley"},
    ]
    filed = dispatch_tool_call(
        "request_change",
        {
            "contact_id": contact.id,
            "payload": {"kind": "patina_override", "items": new_items},
        },
        requester,
        db,
    )

    dispatch_tool_call(
        "resolve_change_request",
        {"request_id": filed["request_id"], "decision": "approve"},
        owner,
        db,
    )
    db.refresh(contact)
    assert contact.patina_overrides is not None
    assert len(contact.patina_overrides) == 2
    assert contact.patina_overrides[0]["text"] == "Ghostbusters"


def test_resolve_blocked_for_non_owner(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    bystander = user_factory(email="charlie@test.fake")
    contact, request_id = _file_off_fly_list(db, owner, requester)

    result = dispatch_tool_call(
        "resolve_change_request",
        {"request_id": request_id, "decision": "approve"},
        bystander,
        db,
    )
    assert result["error"] == "forbidden_owner_only"

    db.refresh(contact)
    assert contact.fly_status != "Off Fly List"
    cr = db.get(ChangeRequest, request_id)
    assert cr is not None
    assert cr.status == "pending"


def test_resolve_already_resolved_request_rejected(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory(email="alice@test.fake")
    requester = user_factory(email="bob@test.fake")
    _, request_id = _file_off_fly_list(db, owner, requester)

    dispatch_tool_call(
        "resolve_change_request",
        {"request_id": request_id, "decision": "approve"},
        owner,
        db,
    )
    # Second resolve attempt — even by the owner — must fail.
    result = dispatch_tool_call(
        "resolve_change_request",
        {"request_id": request_id, "decision": "disapprove"},
        owner,
        db,
    )
    assert result["error"] == "already_resolved"


def test_resolve_unknown_request_returns_not_found(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    result = dispatch_tool_call(
        "resolve_change_request",
        {"request_id": 99999, "decision": "approve"},
        owner,
        db,
    )
    assert result["error"] == "not_found"


def test_resolve_invalid_decision_raises(
    db: Session, user_factory: Callable[..., User]
) -> None:
    owner = user_factory()
    with pytest.raises(ToolDispatchError, match="Invalid params"):
        dispatch_tool_call(
            "resolve_change_request",
            {"request_id": 1, "decision": "maybe"},
            owner,
            db,
        )
