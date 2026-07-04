"""Relationship (edge) model — Phase 5 warm-introduction engine.

Each row is a directed assertion that one contact knows another: the
who-knows-whom graph the intro engine walks. The pathfinder treats edges
as bidirectional for *reachability*, but direction is retained because
some relationship_types are inherently directional (e.g. "introduced_by").

The table starts empty. Edges are populated manually / by CRM import
first, and later auto-populated by transcript/PDF extraction — at which
point `source` and `confidence` distinguish human-asserted edges from
model-inferred ones.

`shared_history` lives here (not on Contact) because it's a property of
the *pair*, not of either person — it's the v1 connection signal:
  none / some / strong  (see Docs/Phase_5_Warm_Intro_Engine.md).
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Relationship(Base):
    """A directed who-knows-whom edge between two contacts."""

    __tablename__ = "relationships"
    __table_args__ = (
        # No self-edges — a contact can't be a relationship to itself.
        CheckConstraint(
            "from_contact_id <> to_contact_id", name="ck_relationship_not_self"
        ),
        # One edge per (from, to, type) — re-asserting the same tie
        # updates in place rather than stacking duplicates.
        UniqueConstraint(
            "from_contact_id",
            "to_contact_id",
            "relationship_type",
            name="uq_relationship_pair_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id"), nullable=False, index=True
    )
    to_contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id"), nullable=False, index=True
    )

    # Category of the tie (colleague, co-investor, board, personal,
    # introduced_by, ...). Default "Unknown" so a bare edge is legal —
    # the v1 connection score doesn't require it.
    relationship_type: Mapped[str] = mapped_column(
        String(50), default="Unknown", server_default="Unknown", nullable=False
    )

    # Coarse strength of shared professional history between the pair —
    # the v1 connection signal. none / some / strong.
    shared_history: Mapped[str] = mapped_column(
        String(20), default="none", server_default="none", nullable=False
    )

    # Provenance: manual / import / extraction. Lets later extraction
    # passes weight model-inferred edges differently from human ones.
    source: Mapped[str] = mapped_column(
        String(50), default="manual", server_default="manual", nullable=False
    )

    # 0.0–1.0 confidence in the edge. Manual edges default to full
    # confidence; extraction will set calibrated lower values.
    confidence: Mapped[float] = mapped_column(
        Float, default=1.0, server_default="1.0", nullable=False
    )

    # Optional free-text context ("co-board at Acme 2019–22", "met at
    # the maritime summit").
    notes: Mapped[str | None] = mapped_column(Text)

    # Who asserted this edge — for audit + future privacy scoping.
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Soft delete — keep removed edges for audit, matching contacts.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
