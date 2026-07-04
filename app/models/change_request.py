"""ChangeRequest model — Phase 2 review queue.

A ChangeRequest is filed by a NON-OWNER teammate who wants a change
applied to a contact they don't own. Today only two kinds:
  - off_fly_list — move the contact to fly_status="Off Fly List"
  - patina_override — replace the contact's patina_overrides list

The contact's owner approves (which applies the change) or disapproves
(which closes the request). Either way an audit row is written.

Status flow:
  pending -> approved   (owner accepted, change applied)
  pending -> disapproved (owner declined, contact unchanged)

Indexes optimize the two common queries:
  - "what's pending across the team" (status='pending')
  - "what's pending for contacts I own" (JOIN on contacts.owner_id)
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # JSONB so the patina_override payload can carry the same shape the
    # frontend already understands. NULL for off_fly_list (no payload).
    payload: Mapped[dict | list | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_cr_status_created", "status", "created_at"),
        Index("ix_cr_contact_status", "contact_id", "status"),
    )
