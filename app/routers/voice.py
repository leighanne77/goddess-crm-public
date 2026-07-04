"""Voice endpoints — Phase 3 Slices 1 (STT) and 4 (TTS).

/transcribe — multipart audio in, transcript JSON out.
/speak       — text JSON in, audio/mpeg bytes out.

Both gated by VOICE_ENABLED=true in Cloud Run env. While the flag is
false the routes return 503 — lets backend code ship to prod without
exposing the endpoints to real users.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.services.voice.speak import speak as do_speak
from app.services.voice.stt_base import (
    STTAudioTooLargeError,
    STTProviderError,
    STTUnsupportedAudioError,
)
from app.services.voice.transcode import (
    ALL_ACCEPTED_CONTENT_TYPES,
    normalize_content_type,
)
from app.services.voice.transcribe import transcribe as do_transcribe
from app.services.voice.tts_base import (
    TTSConfigError,
    TTSEmptyTextError,
    TTSProviderError,
    TTSTextTooLongError,
)

router = APIRouter(prefix="/voice", tags=["voice"])


class TranscribeResponse(BaseModel):
    text: str
    duration_sec: float
    cost_usd: float
    provider: str
    model_id: str


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_endpoint(
    audio: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscribeResponse:
    settings = get_settings()
    if not settings.voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="voice mode not enabled",
        )
    if audio.content_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="audio content-type is required",
        )
    # Browsers (Chrome's MediaRecorder) include codec parameters in
    # Content-Type, e.g. 'audio/webm;codecs=opus'. Normalize before
    # the allow-list check so the parameter doesn't cause a 415.
    normalized = normalize_content_type(audio.content_type)
    # Fast-reject content-types we can't handle — saves reading the
    # whole upload into memory only to fail later. The accepted set
    # includes passthrough formats (WAV/WebM/Ogg/FLAC/MP3) plus
    # browser-native ones we transcode (M4A/MP4).
    if normalized not in ALL_ACCEPTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"content-type {audio.content_type!r} not supported. "
                f"Accepted: {sorted(ALL_ACCEPTED_CONTENT_TYPES)}"
            ),
        )

    audio_bytes = await audio.read()

    try:
        result = do_transcribe(
            audio_bytes,
            content_type=normalized,
            user=user,
            db=db,
        )
    except STTUnsupportedAudioError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except STTAudioTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except STTProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return TranscribeResponse(
        text=result.text,
        duration_sec=result.duration_sec,
        cost_usd=result.cost_usd,
        provider=result.provider,
        model_id=result.model_id,
    )


# ---------------------------------------------------------------------------
# Slice 4 — POST /api/voice/speak
# ---------------------------------------------------------------------------


class SpeakRequest(BaseModel):
    # Limit at the Pydantic layer too so a giant text never reaches the
    # orchestrator's settings-driven cap check (defense in depth).
    text: str = Field(..., min_length=1, max_length=5000)
    voice_id: str | None = None


@router.post(
    "/speak",
    # Audio response — no Pydantic model. Cost / metadata are logged
    # server-side via voice_usage + the structured `tts_speak` log line.
    responses={
        200: {
            "content": {"audio/mpeg": {}},
            "description": "MP3 audio of the synthesized speech.",
        }
    },
)
def speak_endpoint(
    body: SpeakRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    settings = get_settings()
    if not settings.voice_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="voice mode not enabled",
        )

    try:
        result = do_speak(
            body.text,
            user=user,
            db=db,
            voice_id=body.voice_id,
        )
    except TTSEmptyTextError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except TTSTextTooLongError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except TTSConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except TTSProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return Response(
        content=result.audio_bytes,
        media_type=result.content_type,
        # Tiny convenience for the frontend: read cost / voice via
        # headers so a future cost-display widget doesn't need a second
        # round-trip. Server-side logging remains the source of truth.
        headers={
            "X-Voice-Char-Count": str(result.char_count),
            "X-Voice-Cost-Usd": f"{result.cost_usd:.6f}",
            "X-Voice-Provider": result.provider,
            "X-Voice-Voice-Id": result.voice_id,
        },
    )
