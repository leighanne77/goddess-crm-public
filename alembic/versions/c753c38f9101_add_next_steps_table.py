"""add next_steps table

Phase 2 Slice 6.10 — per-contact next-steps activity log. Each row is a
forward-looking todo with its own owner (independent of the contact's
owner — common case: a contact you own with a step assigned to a
teammate to call). Linked to a Google Tasks task on the owner's
"DIN: Next Steps" list so the reminder lives where the owner already
works.

Revision ID: c753c38f9101
Revises: 05cb1c8ae431
Create Date: 2026-05-19 20:08:10.888986
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c753c38f9101"
down_revision: Union[str, None] = "05cb1c8ae431"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "next_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "contact_id",
            sa.Integer(),
            sa.ForeignKey("contacts.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("google_task_id", sa.String(length=128), nullable=True),
        sa.Column("google_task_list_id", sa.String(length=128), nullable=True),
        sa.Column(
            "done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_next_steps_contact_open",
        "next_steps",
        ["contact_id", "done"],
    )


def downgrade() -> None:
    op.drop_index("ix_next_steps_contact_open", table_name="next_steps")
    op.drop_table("next_steps")
