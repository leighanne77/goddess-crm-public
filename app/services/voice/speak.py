"""TTS orchestrator — provider-agnostic glue around any TTSProvider.

Mirrors the transcribe orchestrator (transcribe.py):
- Provider selection from settings (lets tests inject a fake).
- Input validation: empty / too-long text → 400-mapping exceptions.
- Soft daily-budget check on TTS chars: sum today's voice_usage rows
  for mode='tts'; if the user is over their daily char cap, log
  WARNING but still synthesize. Hard enforcement is a later slice.
- Cost computation from char_count + provider's per-1k rate.
- VoiceUsage row write in a single transaction with the caller's
  session.
- Structured `tts_speak` log line for Cloud Logging.

The route layer (app/routers/voice.py) does auth + JSON parsing and
hands `(text, user, db)` to `speak()`. Tests can inject a fake
TTSProvider — see `provider_swap_smoke` in tests/test_voice_tts.py.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, VoiceUsage
from app.services.voice.tts_base import (
    RawAudio,
    TTSEmptyTextError,
    TTSProvider,
    TTSTextTooLongError,
)
from app.services.voice.tts_elevenlabs import TTSElevenLabsProvider

_logger = logging.getLogger("app.voice.speak")


@dataclass(frozen=True)
class SpeakResult:
    """What the API returns to the caller."""

    audio_bytes: bytes
    content_type: str
    char_count: int
    cost_usd: float
    provider: str
    model_id: str
    voice_id: str


def get_default_provider() -> TTSProvider:
    """Build the configured provider from settings.

    Module-level so tests can monkeypatch this to inject a fake
    without touching the orchestrator signature.
    """
    settings = get_settings()
    if settings.tts_provider == "elevenlabs":
        return TTSElevenLabsProvider(
            api_key=settings.elevenlabs_api_key,
            default_voice_id=settings.elevenlabs_voice_id,
            model_id=settings.tts_model,
            speed=settings.elevenlabs_speed,
            stability=settings.elevenlabs_stability,
            similarity_boost=settings.elevenlabs_similarity_boost,
            style=settings.elevenlabs_style,
        )
    raise ValueError(f"unknown tts_provider: {settings.tts_provider}")


def _tts_chars_used_today(db: Session, user_id: int) -> int:
    """Sum char_count for today's TTS rows for this user.

    Uses UTC date for the "today" window. Postgres `date()` against a
    timestamptz column extracts in the session's timezone (UTC for our
    Cloud SQL config); matching with `date.today()` (local) would
    silently drift past UTC midnight.
    """
    today_utc = datetime.now(timezone.utc).date()
    row = db.execute(
        select(func.coalesce(func.sum(VoiceUsage.char_count), 0).label("chars")).where(
            VoiceUsage.user_id == user_id,
            VoiceUsage.mode == "tts",
            func.date(VoiceUsage.ts) == today_utc,
        )
    ).one()
    return int(row.chars)


def speak(
    text: str,
    *,
    user: User,
    db: Session,
    voice_id: str | None = None,
    provider: TTSProvider | None = None,
) -> SpeakResult:
    """End-to-end TTS call. Single DB transaction.

    Raises TTSEmptyTextError / TTSTextTooLongError on bad input,
    TTSConfigError if the provider isn't configured (missing key or
    voice_id), and TTSProviderError on upstream failures. The route
    layer maps these to 400 / 503 / 502 respectively.
    """
    settings = get_settings()

    cleaned = text.strip()
    if not cleaned:
        raise TTSEmptyTextError("text is empty after whitespace strip")
    if len(cleaned) > settings.tts_max_chars_per_call:
        raise TTSTextTooLongError(
            f"text is {len(cleaned)} chars, max is "
            f"{settings.tts_max_chars_per_call} per call"
        )

    # Soft budget check — log but don't block. Use chars BEFORE this
    # call so a single call that pushes the user over still goes
    # through.
    used_chars = _tts_chars_used_today(db, user.id)
    budget = settings.default_daily_tts_chars_budget
    if used_chars >= budget:
        _logger.warning(
            "tts_budget_exceeded",
            extra={
                "event": "tts_budget_exceeded",
                "user_id": user.id,
                "chars_used": used_chars,
                "budget_chars": budget,
            },
        )

    provider = provider or get_default_provider()

    t0 = time.perf_counter()
    raw: RawAudio = provider.speak(cleaned, voice_id=voice_id)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    cost_usd = (raw.char_count / 1000.0) * settings.tts_cost_per_1k_chars_usd

    usage = VoiceUsage(
        user_id=user.id,
        ts=datetime.now(timezone.utc),
        mode="tts",
        provider=raw.provider,
        model_id=raw.model_id,
        duration_sec=None,
        char_count=raw.char_count,
        cost_usd=round(cost_usd, 6),
    )
    db.add(usage)
    db.commit()

    _logger.info(
        "tts_speak",
        extra={
            "event": "tts_speak",
            "user_id": user.id,
            "provider": raw.provider,
            "model_id": raw.model_id,
            "voice_id": raw.voice_id,
            "char_count": raw.char_count,
            "audio_bytes": len(raw.audio_bytes),
            "cost_usd": round(cost_usd, 6),
            "latency_ms": round(latency_ms, 1),
        },
    )

    return SpeakResult(
        audio_bytes=raw.audio_bytes,
        content_type=raw.content_type,
        char_count=raw.char_count,
        cost_usd=round(cost_usd, 6),
        provider=raw.provider,
        model_id=raw.model_id,
        voice_id=raw.voice_id,
    )
