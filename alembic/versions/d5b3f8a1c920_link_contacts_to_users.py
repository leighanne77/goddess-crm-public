"""link contacts to team users (users↔contacts)

Phase 5 warm-intro refinement: add a nullable contacts.user_id FK so a
contact record can be tied to the team *user* it represents (a teammate
who also appears in the network). Lets the warm-intro engine scope paths
to the requester's own relationships and never route an intro through or
to themselves.

Additive + nullable → fast metadata-only column add on Postgres 15. The
one-time backfill matches by email (case-insensitive, trimmed); users.email
is unique so each contact matches at most one user. Auto-linking on new
contacts happens in app/services/user_link.py (mirror of the gov_detect
create-time pattern).

Revision ID: d5b3f8a1c920
Revises: b2e9a4c7d1f3
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d5b3f8a1c920"
down_revision: Union[str, None] = "b2e9a4c7d1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_contacts_user_id_users",
        "contacts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_contacts_user_id", "contacts", ["user_id"])

    # One-time backfill: link each contact to the team user with the same
    # email (case-insensitive, trimmed). Only touches live rows that
    # aren't already linked.
    op.execute(
        """
        UPDATE contacts
        SET user_id = u.id
        FROM users u
        WHERE contacts.email IS NOT NULL
          AND contacts.user_id IS NULL
          AND contacts.deleted_at IS NULL
          AND lower(btrim(contacts.email)) = lower(btrim(u.email))
        """
    )


def downgrade() -> None:
    op.drop_index("ix_contacts_user_id", table_name="contacts")
    op.drop_constraint("fk_contacts_user_id_users", "contacts", type_="foreignkey")
    op.drop_column("contacts", "user_id")
