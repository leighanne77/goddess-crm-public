"""Phase 3 Slice 4 — TTS wrapper service tests.

All provider calls are mocked. The single real-ElevenLabs test is
@pytest.mark.integration and skipped by default; Slice 9 manual smoke
turns it on. `provider_swap_smoke` is the load-bearing test that
locks the TTSProvider interface.
"""

from __future__ import annotations

import logging
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, VoiceUsage
from app.security import create_access_token
from app.services.voice import speak as speak_mod
from app.services.voice.speak import speak as do_speak
from app.services.voice.tts_base import (
    RawAudio,
    TTSConfigError,
    TTSEmptyTextError,
    TTSProviderError,
    TTSTextTooLongError,
)


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


class FakeTTSProvider:
    """Stand-in TTSProvider that returns canned audio and records calls."""

    def __init__(
        self,
        *,
        audio: bytes = b"\xff\xfb\x90fakeaudio",  # MP3 magic-ish
        raise_exc: Exception | None = None,
    ) -> None:
        self.audio = audio
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def speak(self, text: str, *, voice_id: str | None = None) -> RawAudio:
        self.calls.append({"text": text, "voice_id": voice_id})
        if self.raise_exc is not None:
            raise self.raise_exc
        return RawAudio(
            audio_bytes=self.audio,
            content_type="audio/mpeg",
            char_count=len(text),
            provider="fake",
            model_id="fake_model",
            voice_id=voice_id or "fake_default_voice",
        )


@pytest.fixture(autouse=True)
def _enable_voice_and_config(monkeypatch) -> None:
    """Voice endpoint is gated by VOICE_ENABLED; flip it on. Also set
    placeholder ElevenLabs config so the default-provider builder
    doesn't raise TTSConfigError during tests that don't inject a
    provider."""
    settings = get_settings()
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "test_key")
    monkeypatch.setattr(settings, "elevenlabs_voice_id", "test_voice_id")


# ---------------------------------------------------------------------------
# Orchestrator unit tests
# ---------------------------------------------------------------------------


def test_speak_writes_voice_usage_row(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(role="member")
    provider = FakeTTSProvider()

    result = do_speak(
        "hello there",
        user=user,
        db=db,
        provider=provider,
    )

    # 11 chars * $0.18 / 1000 = $0.00198
    assert result.cost_usd == pytest.approx(0.00198, abs=1e-6)
    assert result.content_type == "audio/mpeg"
    assert result.char_count == 11

    rows = (
        db.query(VoiceUsage)
        .filter(VoiceUsage.user_id == user.id, VoiceUsage.mode == "tts")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].provider == "fake"
    assert rows[0].model_id == "fake_model"
    assert rows[0].char_count == 11
    assert rows[0].duration_sec is None  # tts rows leave duration NULL
    assert float(rows[0].cost_usd) == pytest.approx(0.00198, abs=1e-6)


def test_provider_swap_smoke(db: Session, user_factory: Callable[..., User]) -> None:
    """Injecting any TTSProvider-shaped object works end-to-end.
    Locks the interface; if a future swap (Google TTS, OpenAI) needs a
    different signature, this test breaks first."""
    user = user_factory(role="member")
    provider = FakeTTSProvider()

    result = do_speak(
        "lock the interface",
        user=user,
        db=db,
        voice_id="some_other_voice",
        provider=provider,
    )

    assert result.provider == "fake"
    assert provider.calls == [
        {"text": "lock the interface", "voice_id": "some_other_voice"}
    ]


def test_empty_text_raises_empty_error(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(role="member")
    with pytest.raises(TTSEmptyTextError):
        do_speak("   ", user=user, db=db, provider=FakeTTSProvider())


def test_text_over_cap_raises_too_long(
    db: Session, user_factory: Callable[..., User], monkeypatch
) -> None:
    monkeypatch.setattr(get_settings(), "tts_max_chars_per_call", 10)
    user = user_factory(role="member")
    with pytest.raises(TTSTextTooLongError):
        do_speak(
            "this is way too long for the cap",
            user=user,
            db=db,
            provider=FakeTTSProvider(),
        )


def test_over_budget_logs_warning_but_does_not_block(
    db: Session,
    user_factory: Callable[..., User],
    caplog,
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "default_daily_tts_chars_budget", 5)
    user = user_factory(role="member")
    # Pre-seed today's row with 100 chars — already over the 5-char cap.
    from datetime import datetime, timezone

    db.add(
        VoiceUsage(
            user_id=user.id,
            ts=datetime.now(timezone.utc),
            mode="tts",
            provider="fake",
            model_id="fake_model",
            duration_sec=None,
            char_count=100,
            cost_usd=0.018,
        )
    )
    db.commit()

    provider = FakeTTSProvider()
    with caplog.at_level(logging.WARNING, logger="app.voice.speak"):
        result = do_speak("hello", user=user, db=db, provider=provider)

    # Call still went through.
    assert result.char_count == 5
    events = [r for r in caplog.records if r.getMessage() == "tts_budget_exceeded"]
    assert len(events) == 1
    assert events[0].user_id == user.id
    assert events[0].budget_chars == 5


def test_tts_speak_log_line_has_required_fields(
    db: Session, user_factory: Callable[..., User], caplog
) -> None:
    user = user_factory(role="member")
    provider = FakeTTSProvider(audio=b"\x00" * 1234)

    with caplog.at_level(logging.INFO, logger="app.voice.speak"):
        do_speak("structured log test", user=user, db=db, provider=provider)

    events = [r for r in caplog.records if r.getMessage() == "tts_speak"]
    assert len(events) == 1
    e = events[0]
    assert e.event == "tts_speak"
    assert e.user_id == user.id
    assert e.provider == "fake"
    assert e.model_id == "fake_model"
    assert e.char_count == len("structured log test")
    assert e.audio_bytes == 1234
    assert e.cost_usd == pytest.approx(
        len("structured log test") / 1000.0 * 0.18, abs=1e-6
    )
    assert isinstance(e.latency_ms, float)


# ---------------------------------------------------------------------------
# Route layer — POST /api/voice/speak
# ---------------------------------------------------------------------------


def test_unauthenticated_gets_401(client: TestClient) -> None:
    resp = client.post("/api/voice/speak", json={"text": "hi"})
    assert resp.status_code == 401


def test_voice_disabled_returns_503(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "voice_enabled", False)
    user = user_factory(role="member")
    resp = client.post(
        "/api/voice/speak",
        headers=_bearer(user),
        json={"text": "hi"},
    )
    assert resp.status_code == 503


def test_empty_text_returns_400(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    # Pydantic min_length=1 catches at validation time → 422. The
    # orchestrator's whitespace-only check returns 400 for purely
    # whitespace strings that pass min_length.
    monkeypatch.setattr(speak_mod, "get_default_provider", lambda: FakeTTSProvider())
    resp = client.post(
        "/api/voice/speak",
        headers=_bearer(user),
        json={"text": "   "},
    )
    assert resp.status_code == 400


def test_text_too_long_returns_400(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    monkeypatch.setattr(get_settings(), "tts_max_chars_per_call", 10)
    monkeypatch.setattr(speak_mod, "get_default_provider", lambda: FakeTTSProvider())
    resp = client.post(
        "/api/voice/speak",
        headers=_bearer(user),
        json={"text": "this exceeds the cap"},
    )
    assert resp.status_code == 400


def test_provider_502_returns_502(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    monkeypatch.setattr(
        speak_mod,
        "get_default_provider",
        lambda: FakeTTSProvider(raise_exc=TTSProviderError("upstream nope")),
    )
    resp = client.post(
        "/api/voice/speak",
        headers=_bearer(user),
        json={"text": "anything"},
    )
    assert resp.status_code == 502


def test_unconfigured_provider_returns_503(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    """Missing elevenlabs_api_key surfaces as 503, not 500 — same
    posture as voice_enabled=false. Lets ops flip the flag while
    waiting for the key without taking the app down."""
    user = user_factory(role="member")
    monkeypatch.setattr(
        speak_mod,
        "get_default_provider",
        lambda: (_ for _ in ()).throw(TTSConfigError("no key")),
    )
    resp = client.post(
        "/api/voice/speak",
        headers=_bearer(user),
        json={"text": "anything"},
    )
    assert resp.status_code == 503


def test_happy_path_returns_audio_bytes(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    fake = FakeTTSProvider(audio=b"\xff\xfbfake_mp3_bytes_here")
    monkeypatch.setattr(speak_mod, "get_default_provider", lambda: fake)

    resp = client.post(
        "/api/voice/speak",
        headers=_bearer(user),
        json={"text": "hello"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "audio/mpeg"
    assert resp.content == b"\xff\xfbfake_mp3_bytes_here"
    # Metadata headers
    assert resp.headers["x-voice-char-count"] == "5"
    assert resp.headers["x-voice-provider"] == "fake"


# ---------------------------------------------------------------------------
# Provider-internal validation
# ---------------------------------------------------------------------------


def test_elevenlabs_provider_requires_api_key() -> None:
    from app.services.voice.tts_elevenlabs import TTSElevenLabsProvider

    with pytest.raises(TTSConfigError, match="api_key"):
        TTSElevenLabsProvider(api_key="", default_voice_id="v")


def test_elevenlabs_provider_requires_voice_id() -> None:
    from app.services.voice.tts_elevenlabs import TTSElevenLabsProvider

    with pytest.raises(TTSConfigError, match="voice_id"):
        TTSElevenLabsProvider(api_key="k", default_voice_id="")


def test_elevenlabs_provider_sends_voice_settings() -> None:
    """All four configured voice_settings (speed, stability,
    similarity_boost, style) must land on the request body — that's
    how the timbre/speed knobs actually take effect upstream."""
    import httpx

    from app.services.voice.tts_elevenlabs import TTSElevenLabsProvider

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200, content=b"\xff\xfbmp3", headers={"content-type": "audio/mpeg"}
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = TTSElevenLabsProvider(
        api_key="k",
        default_voice_id="v",
        speed=0.85,
        stability=0.3,
        similarity_boost=0.9,
        style=0.4,
        client=mock_client,
    )
    provider.speak("hello")

    assert captured["body"]["voice_settings"] == {
        "speed": 0.85,
        "stability": 0.3,
        "similarity_boost": 0.9,
        "style": 0.4,
    }
    assert captured["body"]["text"] == "hello"


def test_elevenlabs_speed_setting_validates_range() -> None:
    """0.7 ≤ ELEVENLABS_SPEED ≤ 1.0 — outside that, pydantic should
    refuse to construct Settings rather than silently accept a value
    that yields chipmunked or unintelligible audio."""
    import pydantic

    from app.config import Settings

    with pytest.raises(pydantic.ValidationError):
        Settings(elevenlabs_speed=1.5)
    with pytest.raises(pydantic.ValidationError):
        Settings(elevenlabs_speed=0.5)


def test_elevenlabs_timbre_settings_validate_range() -> None:
    """stability, similarity_boost, style are all 0.0–1.0. Values
    outside that range should fail Settings construction up-front."""
    import pydantic

    from app.config import Settings

    for field in (
        "elevenlabs_stability",
        "elevenlabs_similarity_boost",
        "elevenlabs_style",
    ):
        with pytest.raises(pydantic.ValidationError):
            Settings(**{field: 1.5})
        with pytest.raises(pydantic.ValidationError):
            Settings(**{field: -0.1})


# ---------------------------------------------------------------------------
# Integration — gated, runs in Slice 9 manual smoke.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_real_elevenlabs_call_returns_audio() -> None:
    """Real ElevenLabs call. Skipped by default — run with
    `pytest -m integration` when verifying live."""
    pytest.skip("integration test — Slice 9 smoke only")
