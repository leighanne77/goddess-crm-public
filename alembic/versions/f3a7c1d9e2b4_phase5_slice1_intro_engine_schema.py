"""phase5 slice1 intro engine schema — opt_in_status + relationships

Adds the Phase 5 warm-introduction engine's foundation:
  - contacts.opt_in_status (outreach consent gate; default PENDING so
    every existing row backfills to "not yet approved")
  - relationships table (the who-knows-whom edges the pathfinder walks)

The blocklist gate reuses the existing fly_status='Off Fly List'; no new
column for it. Geography is deferred to v2 — no location column here.

Revision ID: f3a7c1d9e2b4
Revises: a8c1f2e3d4b5
Create Date: 2026-06-27
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "f3a7c1d9e2b4"
down_revision: Union[str, None] = "a8c1f2e3d4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Outreach consent gate. NOT NULL with a server default so the
    # existing contacts backfill to PENDING (nobody is offered as an
    # intro path until a human approves them).
    op.add_column(
        "contacts",
        sa.Column(
            "opt_in_status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
    )

    # The who-knows-whom edge table.
    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("from_contact_id", sa.Integer(), nullable=False),
        sa.Column("to_contact_id", sa.Integer(), nullable=False),
        sa.Column(
            "relationship_type",
            sa.String(length=50),
            server_default="Unknown",
            nullable=False,
        ),
        sa.Column(
            "shared_history",
            sa.String(length=20),
            server_default="none",
            nullable=False,
        ),
        sa.Column(
            "source", sa.String(length=50), server_default="manual", nullable=False
        ),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
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
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["from_contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["to_contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "from_contact_id <> to_contact_id", name="ck_relationship_not_self"
        ),
        sa.UniqueConstraint(
            "from_contact_id",
            "to_contact_id",
            "relationship_type",
            name="uq_relationship_pair_type",
        ),
    )
    op.create_index(
        "ix_relationships_from_contact_id", "relationships", ["from_contact_id"]
    )
    op.create_index(
        "ix_relationships_to_contact_id", "relationships", ["to_contact_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_relationships_to_contact_id", table_name="relationships")
    op.drop_index("ix_relationships_from_contact_id", table_name="relationships")
    op.drop_table("relationships")
    op.drop_column("contacts", "opt_in_status")
