"""Phase 3 Slice 0 — voice infrastructure foundation

Three coordinated schema changes for the upcoming voice mode:

1. New table `voice_usage` — one row per STT or TTS call. Columns:
   id, user_id (FK), ts, mode ('stt'|'tts'), provider, model_id,
   duration_sec (NULL for tts rows), char_count (NULL for stt rows),
   cost_usd. Composite index on (user_id, ts) supports the daily-
   aggregate query the soft-budget check runs.

2. New column `audit_log.mode` (String(8), NOT NULL, default 'text').
   Existing rows backfilled to 'text'. New voice writes carry 'voice'.
   Lets admins filter the changelog by modality.

3. New column `users.daily_voice_minutes_budget_override` (Integer,
   NULLABLE). Mirrors the existing daily_input_token_budget_override
   pattern. NULL means "use the global default from settings."

No data migrations beyond the audit_log backfill — voice_usage starts
empty, daily_voice_minutes_budget_override starts NULL for all users.

Revision ID: a8c1f2e3d4b5
Revises: 7b4e2f1a9c83
Create Date: 2026-05-21
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8c1f2e3d4b5"
down_revision: Union[str, None] = "7b4e2f1a9c83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. voice_usage table
    op.create_table(
        "voice_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("mode", sa.String(4), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="0",
        ),
        sa.CheckConstraint(
            "mode IN ('stt', 'tts')",
            name="voice_usage_mode_check",
        ),
    )
    op.create_index(
        "ix_voice_usage_user_ts",
        "voice_usage",
        ["user_id", "ts"],
    )

    # 2. audit_log.mode column — backfill existing rows to 'text'
    op.add_column(
        "audit_log",
        sa.Column(
            "mode",
            sa.String(8),
            nullable=False,
            server_default="text",
        ),
    )

    # 3. users.daily_voice_minutes_budget_override
    op.add_column(
        "users",
        sa.Column(
            "daily_voice_minutes_budget_override",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "daily_voice_minutes_budget_override")
    op.drop_column("audit_log", "mode")
    op.drop_index("ix_voice_usage_user_ts", table_name="voice_usage")
    op.drop_table("voice_usage")
