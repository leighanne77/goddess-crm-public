"""Slice 6.11 — is_gov_employee flag + fly_status rename/default

Three coordinated changes for the gov-employee border + fly-status visual tweaks:

1. New column contacts.is_gov_employee BOOLEAN NOT NULL DEFAULT FALSE.
   Auto-backfilled to TRUE for any existing contact whose email domain
   matches a known government suffix (.gov, .mil, .gc.ca, .gov.uk, etc).
   Owner can toggle off later via update_contact for edge cases (e.g. a
   contractor with a .gov inbox who isn't actually a gov employee).

2. Rename fly_status="Not Sure Yet" → "Maybe Must Fly" in-place. Same
   visual (dotted plane) but the label is more honest — "Not Sure Yet"
   read like a placeholder; "Maybe Must Fly" signals the actual review-
   pending semantics.

3. Change the default fly_status from "Not Sure Yet" to "Unknown".
   New contacts now ship with no plane shown (vs the prior dotted-by-
   default), which the team agreed is the more honest visual — the team
   hasn't decided anything yet, so don't fake the dotted "we're thinking
   about it" affordance.

Revision ID: 7b4e2f1a9c83
Revises: c753c38f9101
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b4e2f1a9c83"
down_revision: Union[str, None] = "c753c38f9101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Government email-domain suffixes recognized by the auto-backfill below.
# Mirrors the runtime detection in app.services.gov_detect — keep in sync.
# Conservative list: false negative is fine (owner can toggle on),
# false positive flags a contact as gov when they aren't.
_GOV_DOMAIN_SUFFIXES = [
    "gov",  # US federal/state (umbrella)
    "mil",  # US military (umbrella)
    "fed.us",  # US federal alternate
    "gc.ca",  # Canada federal
    "gov.uk",  # United Kingdom
    "gov.au",  # Australia
    "gov.sa",  # Saudi Arabia
    "gov.ae",  # United Arab Emirates
    "gov.qa",  # Qatar
    "gov.kw",  # Kuwait
    "gov.sg",  # Singapore
    "gov.in",  # India
    "gov.za",  # South Africa
    "gouv.fr",  # France
    "bund.de",  # Germany federal
]


def upgrade() -> None:
    # 1. Add is_gov_employee column.
    op.add_column(
        "contacts",
        sa.Column(
            "is_gov_employee",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 1a. Backfill is_gov_employee=TRUE for existing contacts whose email
    # domain matches a known government suffix. Two patterns per suffix
    # so we catch both bare (lisa@fed.us → domain == "fed.us") and
    # subdomain (lisa@usace.army.mil → domain ends with ".mil") cases.
    # SPLIT_PART(email, '@', 2) extracts the domain reliably.
    bind = op.get_bind()
    for suffix in _GOV_DOMAIN_SUFFIXES:
        bind.execute(
            sa.text(
                "UPDATE contacts SET is_gov_employee = TRUE WHERE "
                "LOWER(SPLIT_PART(email, '@', 2)) = :exact "
                "OR LOWER(SPLIT_PART(email, '@', 2)) LIKE :sub"
            ),
            {"exact": suffix, "sub": f"%.{suffix}"},
        )

    # 2. Rename "Not Sure Yet" → "Maybe Must Fly" in-place. Same visual
    # (dotted plane); cleaner label.
    bind.execute(
        sa.text(
            "UPDATE contacts SET fly_status = 'Maybe Must Fly' "
            "WHERE fly_status = 'Not Sure Yet'"
        )
    )

    # 3. Flip the column default. New contacts default to "Unknown"
    # (no plane shown) instead of the prior dotted "Not Sure Yet".
    op.alter_column(
        "contacts",
        "fly_status",
        server_default="Unknown",
    )


def downgrade() -> None:
    # Reverse the default first so post-downgrade inserts behave as
    # they did pre-migration.
    op.alter_column(
        "contacts",
        "fly_status",
        server_default="Not Sure Yet",
    )

    bind = op.get_bind()
    # Revert the label rename.
    bind.execute(
        sa.text(
            "UPDATE contacts SET fly_status = 'Not Sure Yet' "
            "WHERE fly_status = 'Maybe Must Fly'"
        )
    )
    # Map any rows still on the new "Unknown" value back to the prior
    # default so downgrade leaves no orphaned values.
    bind.execute(
        sa.text(
            "UPDATE contacts SET fly_status = 'Not Sure Yet' "
            "WHERE fly_status = 'Unknown'"
        )
    )

    op.drop_column("contacts", "is_gov_employee")
