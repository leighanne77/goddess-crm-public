"""STT orchestrator — provider-agnostic glue around any STTProvider.

Responsibilities:
- Provider selection from settings (lets tests inject a fake).
- Soft daily-budget check: sum today's voice_usage.duration_sec for
  the user; if over their budget, log a WARNING but still call the
  provider. Hard enforcement is a later slice.
- Cost computation from duration + provider's per-minute rate.
- VoiceUsage row write (single transaction with the caller's session).
- Structured `stt_transcribe` log line for Cloud Logging.

The route layer (app/routers/voice.py) does auth + multipart parsing
and then hands a `(audio_bytes, content_type, user, db)` tuple to
`transcribe()`. Tests can call `transcribe()` directly with a fake
provider — see `provider_swap_smoke` in tests/test_voice_stt.py.
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
from app.services.voice.stt_base import RawTranscript, STTProvider
from app.services.voice.stt_chirp import STTChirpProvider
from app.services.voice.transcode import (
    TRANSCODE_CONTENT_TYPES,
    normalize_content_type,
    transcode_to_wav,
)

_logger = logging.getLogger("app.voice.transcribe")


@dataclass(frozen=True)
class TranscriptResult:
    """What the API returns to the caller."""

    text: str
    duration_sec: float
    cost_usd: float
    provider: str
    model_id: str


def get_default_provider() -> STTProvider:
    """Build the configured provider from settings.

    Module-level so tests can monkeypatch this to inject a fake without
    touching the orchestrator signature.
    """
    settings = get_settings()
    if settings.stt_provider == "google_chirp":
        # GCP project comes from ADC's quota project, which gcloud /
        # Cloud Run set up. We don't pass it explicitly — the SDK
        # resolves it from the environment.
        from google.auth import default as google_auth_default

        _credentials, project = google_auth_default()
        return STTChirpProvider(
            project=project,
            region=settings.stt_region,
            model=settings.stt_model,
        )
    raise ValueError(f"unknown stt_provider: {settings.stt_provider}")


def _voice_minutes_used_today(db: Session, user_id: int) -> float:
    """Sum duration_sec for today's STT rows for this user.

    Uses UTC date — see _tts_chars_used_today in speak.py for the
    reasoning. Local-date matching against a UTC timestamptz column
    silently drifts past UTC midnight.
    """
    today_utc = datetime.now(timezone.utc).date()
    row = db.execute(
        select(func.coalesce(func.sum(VoiceUsage.duration_sec), 0).label("secs")).where(
            VoiceUsage.user_id == user_id,
            VoiceUsage.mode == "stt",
            func.date(VoiceUsage.ts) == today_utc,
        )
    ).one()
    return float(row.secs) / 60.0


def _user_voice_budget_minutes(user: User) -> int:
    return (
        user.daily_voice_minutes_budget_override
        if user.daily_voice_minutes_budget_override is not None
        else get_settings().default_daily_voice_minutes_budget
    )


def transcribe(
    audio_bytes: bytes,
    *,
    content_type: str,
    user: User,
    db: Session,
    provider: STTProvider | None = None,
) -> TranscriptResult:
    """End-to-end STT call. Single DB transaction.

    Raises STTUnsupportedAudioError / STTAudioTooLargeError /
    STTProviderError on the obvious failure modes — the route layer
    maps these to 415 / 400 / 502 respectively.
    """
    settings = get_settings()
    provider = provider or get_default_provider()

    # Soft budget check — log but don't block. We compute the user's
    # used minutes BEFORE the call so a single call that pushes them
    # over still goes through (no half-billing weirdness).
    used_min = _voice_minutes_used_today(db, user.id)
    budget_min = _user_voice_budget_minutes(user)
    if used_min >= budget_min:
        _logger.warning(
            "voice_budget_exceeded",
            extra={
                "event": "voice_budget_exceeded",
                "user_id": user.id,
                "minutes_used": round(used_min, 2),
                "budget_minutes": budget_min,
            },
        )

    # Slice 2: normalize audio formats Chirp can't decode (M4A from
    # Safari/iOS) by transcoding to WAV server-side. Passthrough for
    # formats the provider handles natively. Strip any MIME parameters
    # (e.g. ';codecs=opus' from Chrome's MediaRecorder) since our
    # set-based dispatch keys on bare MIME types.
    bare_content_type = normalize_content_type(content_type)
    effective_audio = audio_bytes
    effective_content_type = bare_content_type
    if bare_content_type in TRANSCODE_CONTENT_TYPES:
        effective_audio = transcode_to_wav(audio_bytes, bare_content_type)
        effective_content_type = "audio/wav"

    t0 = time.perf_counter()
    raw: RawTranscript = provider.transcribe(
        effective_audio,
        content_type=effective_content_type,
        max_duration_sec=settings.stt_max_duration_sec,
    )
    latency_ms = (time.perf_counter() - t0) * 1000.0

    cost_usd = (raw.duration_sec / 60.0) * settings.stt_cost_per_minute_usd

    usage = VoiceUsage(
        user_id=user.id,
        ts=datetime.now(timezone.utc),
        mode="stt",
        provider=raw.provider,
        model_id=raw.model_id,
        duration_sec=raw.duration_sec,
        char_count=None,
        cost_usd=round(cost_usd, 6),
    )
    db.add(usage)
    db.commit()

    _logger.info(
        "stt_transcribe",
        extra={
            "event": "stt_transcribe",
            "user_id": user.id,
            "provider": raw.provider,
            "model_id": raw.model_id,
            "duration_sec": round(raw.duration_sec, 3),
            "char_count": len(raw.text),
            "cost_usd": round(cost_usd, 6),
            "latency_ms": round(latency_ms, 1),
        },
    )

    return TranscriptResult(
        text=raw.text,
        duration_sec=raw.duration_sec,
        cost_usd=round(cost_usd, 6),
        provider=raw.provider,
        model_id=raw.model_id,
    )
