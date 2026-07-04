"""Phase 3 Slice 2 — server-side audio transcode tests.

ffmpeg is shelled out for real on the happy path. The timeout test
mocks subprocess to simulate a hung ffmpeg. CI runners (ubuntu-latest)
have ffmpeg pre-installed; if a fresh runner ever lacks it, install
it in the workflow before pytest.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.security import create_access_token
from app.services.voice import transcribe as transcribe_mod
from app.services.voice.stt_base import (
    RawTranscript,
    STTAudioTooLargeError,
    STTUnsupportedAudioError,
)
from app.services.voice.transcode import (
    PASSTHROUGH_CONTENT_TYPES,
    TRANSCODE_CONTENT_TYPES,
    transcode_to_wav,
)

FIXTURES = Path(__file__).parent / "fixtures"
M4A_FIXTURE = FIXTURES / "hello.m4a"


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


class _StubProvider:
    """Captures what audio + content_type reach the provider so tests
    can verify the orchestrator routed correctly."""

    def __init__(self) -> None:
        self.received_content_type: str | None = None
        self.received_n_bytes: int | None = None

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        content_type: str,
        max_duration_sec: int,
    ) -> RawTranscript:
        self.received_content_type = content_type
        self.received_n_bytes = len(audio_bytes)
        return RawTranscript(
            text="ok", duration_sec=1.0, provider="stub", model_id="stub"
        )


@pytest.fixture(autouse=True)
def _enable_voice(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "voice_enabled", True)


# ---------------------------------------------------------------------------
# Direct transcode_to_wav() unit tests
# ---------------------------------------------------------------------------


def test_transcode_converts_m4a_to_wav() -> None:
    """Happy path: real M4A in, valid WAV bytes out."""
    assert M4A_FIXTURE.exists(), f"missing fixture: {M4A_FIXTURE}"
    m4a_bytes = M4A_FIXTURE.read_bytes()

    wav = transcode_to_wav(m4a_bytes, "audio/mp4")

    # WAV magic: "RIFF" at byte 0, "WAVE" at byte 8.
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    # Output is non-trivial.
    assert len(wav) > 1000


def test_transcode_rejects_non_transcode_content_type() -> None:
    """transcode_to_wav refuses content-types outside TRANSCODE set —
    the orchestrator should never reach it for passthrough formats."""
    with pytest.raises(STTUnsupportedAudioError):
        transcode_to_wav(b"x", "audio/wav")


def test_transcode_failure_raises_unsupported() -> None:
    """ffmpeg can't decode garbage bytes — returns nonzero exit, which
    we surface as STTUnsupportedAudioError (415 at the route layer)."""
    with pytest.raises(STTUnsupportedAudioError):
        transcode_to_wav(b"this is not audio", "audio/mp4")


def test_transcode_timeout_caps_at_30s() -> None:
    """Mocked subprocess that hangs past 30s → orchestrator surfaces
    a clear error, doesn't leave the request blocked forever."""
    with patch(
        "app.services.voice.transcode.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30),
    ):
        with pytest.raises(STTUnsupportedAudioError, match="timed out"):
            transcode_to_wav(b"x" * 100, "audio/mp4")


def test_passthrough_and_transcode_sets_are_disjoint() -> None:
    """A content-type can't be both passthrough and transcode-needing —
    that would create ambiguity in the orchestrator's routing."""
    assert PASSTHROUGH_CONTENT_TYPES.isdisjoint(TRANSCODE_CONTENT_TYPES)


def test_normalize_content_type_strips_codec_parameter() -> None:
    """Chrome's MediaRecorder produces 'audio/webm;codecs=opus'. The
    bare 'audio/webm' must come out so allow-list lookups work."""
    from app.services.voice.transcode import normalize_content_type

    assert normalize_content_type("audio/webm;codecs=opus") == "audio/webm"
    assert normalize_content_type("audio/webm; codecs=opus") == "audio/webm"
    assert normalize_content_type("AUDIO/WEBM") == "audio/webm"
    assert normalize_content_type("audio/wav") == "audio/wav"
    assert normalize_content_type("audio/ogg;codecs=opus") == "audio/ogg"


def test_route_accepts_webm_with_codec_parameter(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    """Regression test for the Slice 2 first-deploy bug: Chrome sends
    'audio/webm;codecs=opus' which must pass the allow-list and reach
    the provider as the bare 'audio/webm'."""
    user = user_factory(role="member")
    stub = _StubProvider()
    monkeypatch.setattr(transcribe_mod, "get_default_provider", lambda: stub)

    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={
            "audio": ("recording.webm", b"x" * 1024, "audio/webm;codecs=opus"),
        },
    )
    assert resp.status_code == 200, resp.text
    # Provider must have seen the bare type, not the parameterized one.
    assert stub.received_content_type == "audio/webm"


# ---------------------------------------------------------------------------
# Orchestrator routing tests — does transcribe() send the right bytes
# to the provider?
# ---------------------------------------------------------------------------


def test_orchestrator_passes_through_native_format(
    db: Session, user_factory: Callable[..., User]
) -> None:
    """audio/wav input — orchestrator skips ffmpeg, provider sees
    audio/wav and the exact original bytes."""
    user = user_factory(role="member")
    stub = _StubProvider()
    fake_bytes = b"x" * 2048

    transcribe_mod.transcribe(
        fake_bytes,
        content_type="audio/wav",
        user=user,
        db=db,
        provider=stub,
    )

    assert stub.received_content_type == "audio/wav"
    assert stub.received_n_bytes == len(fake_bytes)


def test_orchestrator_transcodes_m4a_before_provider_call(
    db: Session, user_factory: Callable[..., User]
) -> None:
    """audio/mp4 input — orchestrator runs ffmpeg, provider sees
    audio/wav and a different (WAV) byte stream."""
    user = user_factory(role="member")
    stub = _StubProvider()
    m4a_bytes = M4A_FIXTURE.read_bytes()

    transcribe_mod.transcribe(
        m4a_bytes,
        content_type="audio/mp4",
        user=user,
        db=db,
        provider=stub,
    )

    assert stub.received_content_type == "audio/wav"
    # Provider received transcoded bytes, not the M4A input.
    assert stub.received_n_bytes != len(m4a_bytes)
    assert stub.received_n_bytes is not None and stub.received_n_bytes > 0


# ---------------------------------------------------------------------------
# Route-layer allow-list — fast 415 before reading the upload
# ---------------------------------------------------------------------------


def test_route_rejects_unaccepted_content_type_before_transcode(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    """An unsupported content-type (e.g. application/octet-stream) hits
    the route allow-list, not the orchestrator. Important: the call
    must not invoke ffmpeg in this case — we'd be wasting cycles."""
    user = user_factory(role="member")

    # If the orchestrator IS reached, it'll call get_default_provider();
    # raising from there confirms the allow-list caught the request first.
    def boom() -> None:
        raise AssertionError("orchestrator should not be reached")

    monkeypatch.setattr(transcribe_mod, "get_default_provider", boom)

    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={"audio": ("test.bin", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_route_accepts_m4a_and_transcodes(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    """End-to-end through the route: M4A audio in, transcript out.
    Uses a stub provider so we don't hit Chirp."""
    user = user_factory(role="member")
    stub = _StubProvider()
    monkeypatch.setattr(transcribe_mod, "get_default_provider", lambda: stub)

    m4a_bytes = M4A_FIXTURE.read_bytes()
    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={"audio": ("hello.m4a", m4a_bytes, "audio/mp4")},
    )
    assert resp.status_code == 200, resp.text
    # Provider saw the transcoded WAV, not the M4A.
    assert stub.received_content_type == "audio/wav"


def test_oversized_transcode_output_raises_too_large(monkeypatch) -> None:
    """If ffmpeg produces a WAV larger than the sync-recognition limit,
    surface STTAudioTooLargeError (400) instead of letting the provider
    fail unpredictably."""

    class _FakeCompleted:
        returncode = 0
        stdout = b"R" * (10 * 1024 * 1024 + 100)  # > 10 MB
        stderr = b""

    monkeypatch.setattr(
        "app.services.voice.transcode.subprocess.run",
        lambda *a, **kw: _FakeCompleted(),
    )
    with pytest.raises(STTAudioTooLargeError):
        transcode_to_wav(b"input", "audio/mp4")
