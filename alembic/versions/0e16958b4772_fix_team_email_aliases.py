"""fix DIN team email aliases (Pat's primary is alex@)

Revision ID: 0e16958b4772
Revises: e0adf8e90777
Create Date: 2026-04-19 17:32:59.415562

DIN's Google Workspace gives Pat multiple aliases pointing at one
mailbox: alex@example.com and alex@example.com. The
seed migration (9a0665bac0e7) used alex@ as canonical, but
Google's OAuth userinfo response returns alex@ as the *primary*
email — so when she signs in, our auth handler doesn't match the
seeded admin row and creates a brand-new user with the default
'member' role instead.

This migration:
  - Inserts (or promotes) alex@example.com as the canonical
    admin row, idempotent against already-existing rows.
  - Removes the orphaned alex@ row IF it still has no
    google_user_id (i.e. nobody ever signed in as that alias). If
    alex@ has been used to sign in later, we leave it alone.
  - Removes a stale pat@example.com row from earlier testing
    if it has no google_user_id.

Sam Chen and Jordan Blake may have the same alias mismatch when they first
sign in. Apply the same pattern in a follow-up migration if it happens
— don't try to predict their primary alias here.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0e16958b4772"
down_revision: Union[str, None] = "e0adf8e90777"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Insert alex@ as admin if absent. If it already exists (because
    # Pat already signed in as a member), promote it to admin in the
    # second statement.
    op.execute(
        """
        INSERT INTO users (email, name, role, intro_seen, allow_existence_hints)
        VALUES ('alex@example.com', 'Alex Rivera', 'admin', TRUE, TRUE)
        ON CONFLICT (email) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE users
           SET role = 'admin'
         WHERE email = 'alex@example.com' AND role <> 'admin'
        """
    )

    # Reassign any contacts (and change_requests) currently owned by the
    # stale pat@ or orphaned alex@ rows to Pat's actual signed-
    # in account (alex@). Without this, the dummy seed contacts —
    # owned by id=1 pat@ from pre-team-seed testing — are visible to
    # Pat only as "public contacts of someone else", which silently
    # breaks every owner-only action (off-fly-list, patina overrides).
    op.execute(
        """
        UPDATE contacts
           SET owner_id = (SELECT id FROM users WHERE email = 'alex@example.com')
         WHERE owner_id IN (
            SELECT id FROM users
             WHERE email IN ('pat@example.com', 'alex@example.com')
               AND google_user_id IS NULL
         )
        """
    )
    op.execute(
        """
        UPDATE change_requests
           SET requester_id = (
                SELECT id FROM users WHERE email = 'alex@example.com'
           )
         WHERE requester_id IN (
            SELECT id FROM users
             WHERE email IN ('pat@example.com', 'alex@example.com')
               AND google_user_id IS NULL
         )
        """
    )
    op.execute(
        """
        UPDATE change_requests
           SET resolved_by_id = (
                SELECT id FROM users WHERE email = 'alex@example.com'
           )
         WHERE resolved_by_id IN (
            SELECT id FROM users
             WHERE email IN ('pat@example.com', 'alex@example.com')
               AND google_user_id IS NULL
         )
        """
    )

    # Now safe to drop the orphaned seeded alex@ row if unused.
    op.execute(
        """
        DELETE FROM users
         WHERE email = 'alex@example.com'
           AND google_user_id IS NULL
        """
    )

    # And the stale pat@ row from earlier testing.
    op.execute(
        """
        DELETE FROM users
         WHERE email = 'pat@example.com'
           AND google_user_id IS NULL
        """
    )


def downgrade() -> None:
    # Best-effort: remove the canonical alex@ row IFF it has no
    # google_user_id. Don't try to resurrect alex@ — the seed
    # migration's downgrade owns that.
    op.execute(
        """
        DELETE FROM users
         WHERE email = 'alex@example.com'
           AND google_user_id IS NULL
        """
    )
