"""seed three DIN teammates (Alex Rivera admin, Sam Chen + Jordan Blake member)

Revision ID: 9a0665bac0e7
Revises: 68c4c2cd1033
Create Date: 2026-04-19 13:36:41.712813

The DIN team is three people. Each user carries a SYSTEM role (admin /
member, controls UI access) and a FUNCTIONAL role (their job title at
the firm). Phase 1 stores only the system role; functional role lives
in this seed data for now and graduates to a column when Phase 2's
multi-user features need it programmatically.

  Alex Rivera  -> admin  -> Administrator
  Sam Chen       -> member -> Strategy and Industry Lead
  Jordan Blake  -> member -> Investor and Government Relations Lead

intro_seen is pre-set to True because these are already-onboarded
teammates — they don't need to see the welcome intro on first real
login.

The upgrade is idempotent (INSERT ... ON CONFLICT DO NOTHING by email)
so re-running on a DB that already has these rows is safe. Matches the
pattern Day 6 production deploy will need.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "9a0665bac0e7"
down_revision: Union[str, None] = "68c4c2cd1033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TEAMMATES = [
    ("alex@example.com", "Alex Rivera", "admin"),
    ("sam@example.com", "Sam Chen", "member"),
    ("jordan@example.com", "Jordan Blake", "member"),
]


def upgrade() -> None:
    # allow_existence_hints is NOT NULL at the DB level but has only a
    # Python-level default on the model, so we set it explicitly here.
    for email, name, role in TEAMMATES:
        op.execute(
            f"""
            INSERT INTO users (email, name, role, intro_seen, allow_existence_hints)
            VALUES ('{email}', '{name}', '{role}', TRUE, TRUE)
            ON CONFLICT (email) DO NOTHING
            """
        )


def downgrade() -> None:
    emails = "', '".join(e for e, _, _ in TEAMMATES)
    op.execute(f"DELETE FROM users WHERE email IN ('{emails}')")
