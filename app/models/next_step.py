"""NextStep model — Phase 2 Slice 6.10 — per-contact forward-looking todo.

Each next-step belongs to ONE contact and has an OWNER (the teammate who
owes the action). The owner is independent of the contact's owner — the
common case is "Jordan Blake owns Marcus, but Alex Rivera owes the next
call to him." Linked to a Google Tasks task on the owner's "DIN: Next
Steps" list so the reminder shows up where the owner already lives.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NextStep(Base):
    __tablename__ = "next_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id"), nullable=False, index=True
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Google Tasks linkage; NULL means the Tasks API call failed (or
    # was skipped) but the in-app todo still works.
    google_task_id: Mapped[str | None] = mapped_column(String(128))
    google_task_list_id: Mapped[str | None] = mapped_column(String(128))
    done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_next_steps_contact_open", "contact_id", "done"),)
