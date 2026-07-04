"""Audit log model — one row per write performed by an authenticated user."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[int | None] = mapped_column(Integer)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    # Phase 2 Slice 6.9 — action-specific structured metadata for the
    # change log renderer. Shape varies by action:
    #   update_contact -> {"changes": [{"field", "old", "new"}, ...]}
    #   transfer_contact -> {"old_owner_name", "new_owner_name", ...}
    #   resolve_change_request -> {"kind", "decision", "note"}
    #   create_contact -> {"initial_fields": {...subset...}}
    # NULL on rows older than the migration (changelog renderer falls
    # back to the friendly action_label in that case).
    payload_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Phase 3 Slice 0 — modality of the write. 'text' for typed input
    # (the historical default; all pre-Phase-3 rows are 'text'), 'voice'
    # for writes triggered by a spoken transcript. Lets admins filter
    # "show only voice activity" or "show only text" in the change log.
    mode: Mapped[str] = mapped_column(String(8), nullable=False, server_default="text")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_audit_user_created", "user_id", "created_at"),)
