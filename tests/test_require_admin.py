"""Tests for the require_admin dependency.

require_admin gates endpoints behind system-role admin. It layers on top
of get_current_user, so the same Bearer-or-cookie auth applies; this
just adds the role check. Tested by calling the dependency directly —
no need to spin up a router since the logic is a single role compare.
"""

from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies import require_admin
from app.models import User


def test_require_admin_allows_admin_user(
    db: Session, user_factory: Callable[..., User]
) -> None:
    admin = user_factory(email="admin@test.fake", role="admin")
    assert require_admin(current_user=admin) is admin


def test_require_admin_rejects_member_user(
    db: Session, user_factory: Callable[..., User]
) -> None:
    member = user_factory(email="member@test.fake", role="member")
    with pytest.raises(HTTPException) as exc_info:
        require_admin(current_user=member)
    assert exc_info.value.status_code == 403
    assert "admin" in exc_info.value.detail.lower()


@pytest.mark.parametrize("bad_role", ["Admin", "ADMIN", "superuser", "", "owner"])
def test_require_admin_rejects_unknown_role(
    db: Session, user_factory: Callable[..., User], bad_role: str
) -> None:
    """Anything other than exactly 'admin' is rejected — no fuzzy matching.

    Case sensitivity matters: 'Admin' is not 'admin'. Keeps the contract
    predictable and avoids accidental elevation from a case-insensitive
    DB collation somewhere downstream.
    """
    user = user_factory(email=f"role_{bad_role or 'empty'}@test.fake", role=bad_role)
    with pytest.raises(HTTPException) as exc_info:
        require_admin(current_user=user)
    assert exc_info.value.status_code == 403
