"""add metro to contacts

Phase 5 geography: a free-text metro / city for the warm-introduction
engine's same-metro connection signal. Nullable, additive.

Revision ID: b2e9a4c7d1f3
Revises: f3a7c1d9e2b4
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "b2e9a4c7d1f3"
down_revision: Union[str, None] = "f3a7c1d9e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("metro", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "metro")
