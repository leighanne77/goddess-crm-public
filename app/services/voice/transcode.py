"""Server-side audio transcoding via ffmpeg.

Phase 3 Slice 2. Browsers produce different audio formats (Safari M4A,
Chrome WebM/Opus, Firefox Ogg/Opus). Chirp 2 silently returns no
results for M4A — see Slice 0 bake-off (`Docs/Lessons_Learned.md`).
Rather than gate the team out of Safari/iOS, we normalize every voice
upload to LINEAR16 WAV (16kHz mono) before the provider call.

Implementation: shell out to ffmpeg via subprocess.run, streaming
input via stdin and capturing output from stdout. No tempfiles. 30s
hard timeout — sync recognition only accepts 60s of audio, so transcode
can't reasonably need more than half that.
"""

from __future__ import annotations

import subprocess
from typing import FrozenSet

from app.services.voice.stt_base import STTAudioTooLargeError, STTUnsupportedAudioError

# Content-types where the provider's AutoDetectDecodingConfig
# successfully decodes the bytes as-is. Skipping transcode for these
# saves a subprocess round-trip per call.
PASSTHROUGH_CONTENT_TYPES: FrozenSet[str] = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/webm",
        "audio/ogg",
        "audio/flac",
        "audio/mpeg",
        "audio/mp3",
    }
)

# Content-types we'll accept from the browser via transcode. M4A / MP4
# is what Safari's MediaRecorder produces by default.
TRANSCODE_CONTENT_TYPES: FrozenSet[str] = frozenset(
    {
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
    }
)

ALL_ACCEPTED_CONTENT_TYPES: FrozenSet[str] = (
    PASSTHROUGH_CONTENT_TYPES | TRANSCODE_CONTENT_TYPES
)


def normalize_content_type(content_type: str) -> str:
    """Strip MIME parameters so 'audio/webm;codecs=opus' → 'audio/webm'.

    Browsers (Chrome's MediaRecorder in particular) include codec
    parameters that aren't part of the bare MIME type our allow-lists
    are keyed on. Lowercased for case-insensitive comparison.
    """
    return content_type.split(";", 1)[0].strip().lower()


_FFMPEG_BIN = "ffmpeg"
_TRANSCODE_TIMEOUT_SEC = 30
_MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # mirrors the provider's sync limit


def transcode_to_wav(audio_bytes: bytes, source_content_type: str) -> bytes:
    """Convert audio bytes to LINEAR16 WAV (16kHz mono) via ffmpeg.

    Raises STTUnsupportedAudioError if the source content-type isn't
    in TRANSCODE_CONTENT_TYPES, or if ffmpeg can't decode the input.
    Raises STTAudioTooLargeError if the resulting WAV exceeds the
    provider's sync-recognition limit (10 MB).
    """
    if source_content_type not in TRANSCODE_CONTENT_TYPES:
        raise STTUnsupportedAudioError(
            f"transcode does not handle {source_content_type!r}; "
            f"expected one of {sorted(TRANSCODE_CONTENT_TYPES)}"
        )

    try:
        completed = subprocess.run(
            [
                _FFMPEG_BIN,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                _ffmpeg_input_format(source_content_type),
                "-i",
                "pipe:0",
                "-ac",
                "1",  # mono
                "-ar",
                "16000",  # 16kHz
                "-acodec",
                "pcm_s16le",
                "-f",
                "wav",
                "pipe:1",
            ],
            input=audio_bytes,
            capture_output=True,
            timeout=_TRANSCODE_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise STTUnsupportedAudioError(
            f"ffmpeg timed out after {_TRANSCODE_TIMEOUT_SEC}s"
        ) from exc

    if completed.returncode != 0:
        # ffmpeg's stderr explains what went wrong. We don't pass it
        # back to the user (it's noisy and exposes implementation
        # details), but it's useful in the server logs.
        stderr = completed.stderr.decode("utf-8", errors="replace")[:500]
        raise STTUnsupportedAudioError(
            f"ffmpeg failed to decode {source_content_type!r}: {stderr}"
        )

    wav_bytes = completed.stdout
    if len(wav_bytes) > _MAX_OUTPUT_BYTES:
        raise STTAudioTooLargeError(
            f"transcoded WAV is {len(wav_bytes):,} bytes, "
            f"exceeds {_MAX_OUTPUT_BYTES:,} sync-recognition limit"
        )

    return wav_bytes


def _ffmpeg_input_format(content_type: str) -> str:
    """Map content-type to ffmpeg's `-f` input-format hint.

    ffmpeg can usually auto-detect, but supplying the hint avoids edge
    cases when the container's magic bytes are non-standard.
    """
    if content_type in ("audio/mp4", "audio/m4a", "audio/x-m4a"):
        return "mp4"
    # Defensive: shouldn't reach here given the gate at the top.
    return content_type.split("/")[-1]
