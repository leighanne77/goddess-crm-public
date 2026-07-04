"""Provider-agnostic text-to-speech interface.

Mirrors the STTProvider pattern in stt_base.py. Each TTS provider
returns a `RawAudio`; the orchestrator (speak.py) handles cost, soft
budget, voice_usage row writes, and structured logging.

Slice 4 ships `TTSElevenLabsProvider`. Future swaps (Google TTS,
OpenAI TTS, Resemble) drop in by writing one module that implements
`TTSProvider` and flipping `settings.tts_provider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawAudio:
    """What a TTS provider returns. Cost is computed by the orchestrator."""

    audio_bytes: bytes
    content_type: str  # e.g. "audio/mpeg", "audio/ogg"
    char_count: int  # input text length, the billing dimension
    provider: str
    model_id: str
    voice_id: str


class TTSEmptyTextError(ValueError):
    """Caller passed empty / whitespace-only text. Maps to 400."""


class TTSTextTooLongError(ValueError):
    """Caller passed text exceeding the per-call cap. Maps to 400."""


class TTSConfigError(RuntimeError):
    """Provider not configured (missing API key or voice id). Maps to 503."""


class TTSProviderError(RuntimeError):
    """Upstream provider returned an error. Maps to 502."""


class TTSProvider(Protocol):
    """Text in, audio bytes out. Sync, single call."""

    def speak(self, text: str, *, voice_id: str | None = None) -> RawAudio: ...
