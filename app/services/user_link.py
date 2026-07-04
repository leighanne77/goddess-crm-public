"""Link a contact record to the team user it represents, by email match.

Used by create_contact (chat tool + REST) to auto-set contacts.user_id
when a contact's email matches a team user's — the "this contact record
*is* teammate X" link. Kept parallel to app/services/gov_detect.py
(auto-set a field from the email on create) + a one-time backfill in
migration d5b3f8a1c920.

Why: the warm-intro engine uses this link to start paths from the
requester's *own* contact node (their relationships) rather than
firm-wide, and to avoid routing an intro through or to the requester.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def user_id_for_email(db: Session, email: str | None) -> int | None:
    """Return the id of the team user whose email matches `email`
    (case-insensitive, trimmed), or None if there's no email or no match.

    users.email is unique, so there is at most one match — safe to use as
    the contact→user link.
    """
    if not email or "@" not in email:
        return None
    normalized = email.strip().lower()
    return db.scalar(
        select(User.id).where(func.lower(func.trim(User.email)) == normalized)
    )
