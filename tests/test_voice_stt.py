"""Phase 3 Slice 1 — STT wrapper service.

All provider calls are mocked. The one real-Chirp test is marked
@pytest.mark.integration and skipped by default; Slice 9 turns it on
in manual smoke. The `provider_swap_smoke` test is the load-bearing
one — it locks the STTProvider interface so the future Whisper / local
swap stays a one-file change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, VoiceUsage
from app.security import create_access_token
from app.services.voice import transcribe as transcribe_mod
from app.services.voice.stt_base import (
    RawTranscript,
    STTAudioTooLargeError,
    STTProviderError,
    STTUnsupportedAudioError,
)
from app.services.voice.transcribe import transcribe as do_transcribe


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


class FakeProvider:
    """Stand-in STTProvider that returns canned output and records calls."""

    def __init__(
        self,
        *,
        text: str = "hello world",
        duration_sec: float = 4.0,
        raise_exc: Exception | None = None,
    ) -> None:
        self.text = text
        self.duration_sec = duration_sec
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        content_type: str,
        max_duration_sec: int,
    ) -> RawTranscript:
        self.calls.append(
            {
                "n_bytes": len(audio_bytes),
                "content_type": content_type,
                "max_duration_sec": max_duration_sec,
            }
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return RawTranscript(
            text=self.text,
            duration_sec=self.duration_sec,
            provider="fake",
            model_id="fake_model",
        )


@pytest.fixture(autouse=True)
def _enable_voice(monkeypatch) -> None:
    """Voice endpoint is gated by VOICE_ENABLED; flip it on per test."""
    monkeypatch.setattr(get_settings(), "voice_enabled", True)


# ---------------------------------------------------------------------------
# Orchestrator unit tests (call transcribe() directly with a FakeProvider)
# ---------------------------------------------------------------------------


def test_transcribe_writes_voice_usage_row(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(role="member")
    provider = FakeProvider(text="hello world", duration_sec=4.0)

    result = do_transcribe(
        b"x" * 1024,
        content_type="audio/wav",
        user=user,
        db=db,
        provider=provider,
    )

    assert result.text == "hello world"
    assert result.duration_sec == 4.0
    # 4 sec * $0.024 / 60 = $0.0016
    assert result.cost_usd == pytest.approx(0.0016, abs=1e-6)

    rows = (
        db.query(VoiceUsage)
        .filter(VoiceUsage.user_id == user.id)
        .order_by(VoiceUsage.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].mode == "stt"
    assert rows[0].provider == "fake"
    assert rows[0].model_id == "fake_model"
    assert rows[0].duration_sec == 4.0
    assert float(rows[0].cost_usd) == pytest.approx(0.0016, abs=1e-6)


def test_provider_swap_smoke(db: Session, user_factory: Callable[..., User]) -> None:
    """Inject any STTProvider-compatible object; orchestrator handles it.

    Locks the interface — if a future swap (Whisper, local) needs a
    new method or different signature, this test breaks first.
    """
    user = user_factory(role="member")
    provider = FakeProvider(text="anything", duration_sec=2.5)

    result = do_transcribe(
        b"audio",
        content_type="audio/wav",
        user=user,
        db=db,
        provider=provider,
    )

    assert result.provider == "fake"
    assert result.model_id == "fake_model"
    # Provider received exactly what we expect from the orchestrator.
    assert provider.calls == [
        {
            "n_bytes": 5,
            "content_type": "audio/wav",
            "max_duration_sec": get_settings().stt_max_duration_sec,
        }
    ]


def test_over_budget_logs_warning_but_does_not_block(
    db: Session, user_factory: Callable[..., User], caplog
) -> None:
    user = user_factory(role="member")
    user.daily_voice_minutes_budget_override = 1  # 1 minute/day
    db.commit()

    # Pre-seed 90 seconds of voice usage today — already over the 1-min cap.
    db.add(
        VoiceUsage(
            user_id=user.id,
            ts=datetime.now(timezone.utc),
            mode="stt",
            provider="fake",
            model_id="fake_model",
            duration_sec=90.0,
            cost_usd=0.036,
        )
    )
    db.commit()

    provider = FakeProvider()
    with caplog.at_level(logging.WARNING, logger="app.voice.transcribe"):
        result = do_transcribe(
            b"audio",
            content_type="audio/wav",
            user=user,
            db=db,
            provider=provider,
        )

    # Call still went through.
    assert result.text == "hello world"
    # And we logged a budget warning.
    budget_events = [
        r for r in caplog.records if r.getMessage() == "voice_budget_exceeded"
    ]
    assert len(budget_events) == 1
    assert budget_events[0].user_id == user.id
    assert budget_events[0].budget_minutes == 1


def test_under_budget_emits_no_warning(
    db: Session, user_factory: Callable[..., User], caplog
) -> None:
    user = user_factory(role="member")  # default 60-min budget
    provider = FakeProvider()

    with caplog.at_level(logging.WARNING, logger="app.voice.transcribe"):
        do_transcribe(
            b"audio",
            content_type="audio/wav",
            user=user,
            db=db,
            provider=provider,
        )

    budget_events = [
        r for r in caplog.records if r.getMessage() == "voice_budget_exceeded"
    ]
    assert budget_events == []


def test_stt_transcribe_log_line_has_required_fields(
    db: Session, user_factory: Callable[..., User], caplog
) -> None:
    user = user_factory(role="member")
    provider = FakeProvider(text="some words here", duration_sec=3.0)

    with caplog.at_level(logging.INFO, logger="app.voice.transcribe"):
        do_transcribe(
            b"audio",
            content_type="audio/wav",
            user=user,
            db=db,
            provider=provider,
        )

    events = [r for r in caplog.records if r.getMessage() == "stt_transcribe"]
    assert len(events) == 1
    e = events[0]
    assert e.event == "stt_transcribe"
    assert e.user_id == user.id
    assert e.provider == "fake"
    assert e.model_id == "fake_model"
    assert e.duration_sec == 3.0
    assert e.char_count == len("some words here")
    assert e.cost_usd == pytest.approx(0.0012, abs=1e-6)
    assert isinstance(e.latency_ms, float)


# ---------------------------------------------------------------------------
# Route layer (POST /api/voice/transcribe) — auth, status codes
# ---------------------------------------------------------------------------


def test_unauthenticated_gets_401(client: TestClient) -> None:
    resp = client.post(
        "/api/voice/transcribe",
        files={"audio": ("test.wav", b"x", "audio/wav")},
    )
    assert resp.status_code == 401


def test_voice_disabled_returns_503(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    """When VOICE_ENABLED is false, the route returns 503 before any
    provider call."""
    monkeypatch.setattr(get_settings(), "voice_enabled", False)
    user = user_factory(role="member")

    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={"audio": ("test.wav", b"x", "audio/wav")},
    )
    assert resp.status_code == 503


def test_unsupported_content_type_returns_415(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    provider = FakeProvider(raise_exc=STTUnsupportedAudioError("nope"))
    monkeypatch.setattr(transcribe_mod, "get_default_provider", lambda: provider)

    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={"audio": ("test.bin", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_too_large_audio_returns_400(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    provider = FakeProvider(
        raise_exc=STTAudioTooLargeError("audio is 99 MB, max is 10")
    )
    monkeypatch.setattr(transcribe_mod, "get_default_provider", lambda: provider)

    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={"audio": ("big.wav", b"x" * 1024, "audio/wav")},
    )
    assert resp.status_code == 400


def test_provider_500_returns_502(
    client: TestClient,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    provider = FakeProvider(raise_exc=STTProviderError("upstream went pop"))
    monkeypatch.setattr(transcribe_mod, "get_default_provider", lambda: provider)

    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={"audio": ("test.wav", b"x", "audio/wav")},
    )
    assert resp.status_code == 502


def test_happy_path_returns_transcript(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    user = user_factory(role="member")
    provider = FakeProvider(text="lisa grossman at the army corps", duration_sec=6.0)
    monkeypatch.setattr(transcribe_mod, "get_default_provider", lambda: provider)

    resp = client.post(
        "/api/voice/transcribe",
        headers=_bearer(user),
        files={"audio": ("test.wav", b"x" * 2048, "audio/wav")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["text"] == "lisa grossman at the army corps"
    assert body["duration_sec"] == 6.0
    # 6 sec * $0.024 / 60 = $0.0024
    assert body["cost_usd"] == pytest.approx(0.0024, abs=1e-6)
    assert body["provider"] == "fake"
    assert body["model_id"] == "fake_model"


# ---------------------------------------------------------------------------
# Provider-internal validation (Chirp-side rejects before any RPC)
# ---------------------------------------------------------------------------


def test_chirp_rejects_unsupported_content_type() -> None:
    from app.services.voice.stt_chirp import STTChirpProvider

    # Pass a sentinel client — we shouldn't even reach it.
    chirp = STTChirpProvider(
        project="p", region="us-central1", client=object()  # type: ignore[arg-type]
    )
    with pytest.raises(STTUnsupportedAudioError):
        chirp.transcribe(
            b"x",
            content_type="application/octet-stream",
            max_duration_sec=60,
        )


def test_chirp_rejects_oversized_payload() -> None:
    from app.services.voice.stt_chirp import STTChirpProvider

    chirp = STTChirpProvider(
        project="p", region="us-central1", client=object()  # type: ignore[arg-type]
    )
    too_big = b"x" * (10 * 1024 * 1024 + 1)
    with pytest.raises(STTAudioTooLargeError):
        chirp.transcribe(too_big, content_type="audio/wav", max_duration_sec=60)


# ---------------------------------------------------------------------------
# Integration test — gated; runs in Slice 9 manual smoke.
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_real_chirp_call_returns_transcript() -> None:
    """Real Chirp 2 call against a small canned WAV. Skipped by
    default; run with `pytest -m integration` when verifying live."""
    pytest.skip("integration test — Slice 9 smoke only")
