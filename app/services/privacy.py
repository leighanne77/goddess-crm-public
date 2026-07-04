"""Row-level privacy for contacts.

Three states of visibility, in order from least to most restrictive:

1. **Visible** — full row. Caller is either the owner, a sharee, or the
   contact is public. Use `visible_contacts_query`.

2. **Redacted** (Phase 2 Slice 6.5) — partial row. Caller is NOT the
   owner / sharee, the contact IS private, AND the owner has
   `allow_existence_hints=True` (default). The caller learns only the
   columns named in `contact.reveal_fields` (default: primary_fund,
   company_name, sectors) plus the owner's name + initials so they
   know whom to ask. Use `redactable_contacts_query`. PII (name, email,
   phones, notes, title, image_url) is NEVER in reveal_fields and
   never leaks via this path.

3. **Hidden** — row excluded entirely. Caller is non-owner / non-sharee,
   contact is private, AND owner has `allow_existence_hints=False`.
   Neither query yields the row; caller cannot infer its existence.

Every endpoint that reads contacts must start from one of these two
queries — no raw select(Contact) calls allowed outside this module.
"""

from sqlalchemy import Select, or_, select

from app.models import Contact, User


def visible_contacts_query(current_user: User) -> Select[tuple[Contact]]:
    """Return a Select that yields only contacts the user can see in full."""
    return select(Contact).where(
        Contact.deleted_at.is_(None),
        or_(
            Contact.is_private.is_(False),
            Contact.owner_id == current_user.id,
            Contact.shared_with.any(current_user.id),
        ),
    )


def redactable_contacts_query(current_user: User) -> Select[tuple[Contact]]:
    """Return a Select that yields contacts the caller may see in REDACTED
    form only — private contacts owned by a teammate who allows existence
    hints. The caller must not be the owner or a sharee (those rows come
    through `visible_contacts_query` instead).

    Search handlers union these rows with the visible ones, applying
    reveal-field-aware filters to decide whether a redacted row actually
    matches the query. SEE `app/services/tool_dispatch._redacted_row_matches`.
    """
    return (
        select(Contact)
        .join(User, User.id == Contact.owner_id)
        .where(
            Contact.deleted_at.is_(None),
            Contact.is_private.is_(True),
            Contact.owner_id != current_user.id,
            ~Contact.shared_with.any(current_user.id),
            User.allow_existence_hints.is_(True),
        )
    )
