"""add reveal_fields for partial-reveal privacy

Phase 2 Slice 6.5. Adds contacts.reveal_fields TEXT[] — the set of
columns visible on a private contact when a non-owner teammate sees it.
Default `{primary_fund, company_name, sectors}` covers the common
"Alex Rivera has someone in Energy at ADIA" case without exposing PII
(name, email, phones, notes, title, image_url).

Backfill: all existing rows get the default. The column is NOT NULL —
the safe path is to always have a definite reveal set rather than
treating NULL as a special case in code.

Revision ID: 11935709768a
Revises: d4f8a91c2e07
Create Date: 2026-05-19 16:12:42.027353
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "11935709768a"
down_revision: Union[str, None] = "d4f8a91c2e07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_REVEAL_FIELDS = "{primary_fund,company_name,sectors}"


def upgrade() -> None:
    # Add the column nullable first so existing rows can be backfilled
    # without violating the constraint, then enforce NOT NULL.
    op.add_column(
        "contacts",
        sa.Column(
            "reveal_fields",
            sa.ARRAY(sa.String(length=50)),
            nullable=True,
            server_default=DEFAULT_REVEAL_FIELDS,
        ),
    )
    # Backfill any pre-existing rows (server_default only applies to
    # NEW inserts in some Postgres versions; explicit UPDATE is safe).
    op.execute(
        f"UPDATE contacts SET reveal_fields = '{DEFAULT_REVEAL_FIELDS}'::text[] "
        "WHERE reveal_fields IS NULL"
    )
    op.alter_column("contacts", "reveal_fields", nullable=False)


def downgrade() -> None:
    op.drop_column("contacts", "reveal_fields")
