"""encrypt google tokens at rest

Widens google_access_token / google_refresh_token to VARCHAR(1024) to
fit Fernet ciphertext overhead, then encrypts any existing plaintext
rows in place. Idempotent: rows that already start with the Fernet
'gAAAAA' prefix are skipped.

Revision ID: d4f8a91c2e07
Revises: e2fb002d701d
Create Date: 2026-05-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.services import token_crypto

revision: str = "d4f8a91c2e07"
down_revision: Union[str, None] = "e2fb002d701d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "google_access_token",
        existing_type=sa.String(length=500),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )
    op.alter_column(
        "users",
        "google_refresh_token",
        existing_type=sa.String(length=500),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, google_access_token, google_refresh_token "
            "FROM users "
            "WHERE google_access_token IS NOT NULL "
            "   OR google_refresh_token IS NOT NULL"
        )
    ).fetchall()

    for row in rows:
        updates: dict[str, str] = {}
        if row.google_access_token and not token_crypto.looks_encrypted(
            row.google_access_token
        ):
            updates["google_access_token"] = token_crypto.encrypt(
                row.google_access_token
            )
        if row.google_refresh_token and not token_crypto.looks_encrypted(
            row.google_refresh_token
        ):
            updates["google_refresh_token"] = token_crypto.encrypt(
                row.google_refresh_token
            )
        if not updates:
            continue
        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        bind.execute(
            sa.text(f"UPDATE users SET {set_clause} WHERE id = :id"),
            {**updates, "id": row.id},
        )


def downgrade() -> None:
    # Decrypt rows back to plaintext before narrowing the column. Same
    # idempotency check: skip anything that isn't a Fernet token.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, google_access_token, google_refresh_token "
            "FROM users "
            "WHERE google_access_token IS NOT NULL "
            "   OR google_refresh_token IS NOT NULL"
        )
    ).fetchall()

    for row in rows:
        updates: dict[str, str] = {}
        if row.google_access_token and token_crypto.looks_encrypted(
            row.google_access_token
        ):
            updates["google_access_token"] = token_crypto.decrypt(
                row.google_access_token
            )
        if row.google_refresh_token and token_crypto.looks_encrypted(
            row.google_refresh_token
        ):
            updates["google_refresh_token"] = token_crypto.decrypt(
                row.google_refresh_token
            )
        if not updates:
            continue
        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        bind.execute(
            sa.text(f"UPDATE users SET {set_clause} WHERE id = :id"),
            {**updates, "id": row.id},
        )

    op.alter_column(
        "users",
        "google_refresh_token",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "users",
        "google_access_token",
        existing_type=sa.String(length=1024),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
