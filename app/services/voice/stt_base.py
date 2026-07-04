"""Provider-agnostic speech-to-text interface.

The `STTProvider` protocol lets us swap STT backends (Chirp, Whisper,
local Whisper) without touching the orchestrator or the API route. Each
provider returns a `RawTranscript`; the orchestrator handles cost,
budget checks, voice_usage row writes, and structured logging.

Slice 1 ships `STTChirpProvider`. A future Whisper swap means writing
one new module that implements `STTProvider` and flipping
`settings.stt_provider`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawTranscript:
    """What a provider returns. Cost is computed by the orchestrator."""

    text: str
    duration_sec: float
    provider: str
    model_id: str


class STTUnsupportedAudioError(ValueError):
    """Audio content-type the provider can't decode. Maps to 415."""


class STTAudioTooLargeError(ValueError):
    """Audio exceeds the provider's size or duration limit. Maps to 400."""


class STTProviderError(RuntimeError):
    """Upstream provider returned an error. Maps to 502."""


class STTProvider(Protocol):
    """One audio blob in, one transcript out. Sync, single-call."""

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        content_type: str,
        max_duration_sec: int,
    ) -> RawTranscript: ...
