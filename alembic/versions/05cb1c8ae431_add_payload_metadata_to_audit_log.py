"""add payload_metadata to audit_log

Phase 2 Slice 6.9 — field-level change log. Adds a nullable JSONB column
that each write handler populates with action-specific shape (for
update_contact: a `changes` list with field/old/new; for transfer: old +
new owner; for resolve_change_request: kind + decision; etc). Older
rows (created before this migration) keep NULL — the changelog renderer
falls back to the friendly action_label for those.

Revision ID: 05cb1c8ae431
Revises: 11935709768a
Create Date: 2026-05-19 19:07:43.692361
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "05cb1c8ae431"
down_revision: Union[str, None] = "11935709768a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column(
            "payload_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("audit_log", "payload_metadata")
