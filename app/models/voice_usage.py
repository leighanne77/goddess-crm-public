"""VoiceUsage model — one row per STT or TTS call.

Per-call rows let the soft-budget check (Phase 3 Slice 1) and the
cost-alert job (Slice 7.1 extension) aggregate today's usage via a
single GROUP BY query, rather than maintaining a counter column that
needs daily reset.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VoiceUsage(Base):
    __tablename__ = "voice_usage"
    __table_args__ = (
        CheckConstraint("mode IN ('stt', 'tts')", name="voice_usage_mode_check"),
        Index("ix_voice_usage_user_ts", "user_id", "ts"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    mode: Mapped[str] = mapped_column(String(4), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # NULL on tts rows (no input audio).
    duration_sec: Mapped[float | None] = mapped_column(Float)
    # NULL on stt rows (no output text).
    char_count: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, server_default="0"
    )
