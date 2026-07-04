"""Tests for the admin /cost-summary endpoint."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User
from app.security import create_access_token


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


def _seed_usage(
    db: Session,
    user: User,
    *,
    input_tokens: int,
    output_tokens: int,
    reset_at: date,
) -> None:
    """Backfill token counters on an existing user row and commit."""
    user.daily_input_tokens_used = input_tokens
    user.daily_output_tokens_used = output_tokens
    user.token_budget_reset_at = reset_at
    db.commit()


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def test_member_gets_403(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    member = user_factory(role="member")
    resp = client.get("/api/admin/cost-summary", headers=_bearer(member))
    assert resp.status_code == 403


def test_unauthenticated_gets_401(client: TestClient) -> None:
    resp = client.get("/api/admin/cost-summary")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------


def test_spend_math_is_correct_for_sonnet_4_6(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Sonnet 4.6 list pricing: $3/M input, $15/M output. 1M in + 1M out = $18."""
    admin = user_factory(role="admin")
    _seed_usage(
        db,
        admin,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        reset_at=date.today(),
    )

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["input_tokens"] == 1_000_000
    assert body["output_tokens"] == 1_000_000
    assert body["spend_usd"] == 18.0
    assert body["model"] == "claude-sonnet-4-6"


def test_over_threshold_flag_fires_at_or_above_threshold(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    """Default threshold is $10/day; flip it lower to exercise the flag."""
    monkeypatch.setattr(get_settings(), "daily_cost_alert_threshold_usd", 0.50)

    admin = user_factory(role="admin")
    # 100k input + 20k output = 100k * 3/1M + 20k * 15/1M = $0.30 + $0.30 = $0.60
    _seed_usage(
        db, admin, input_tokens=100_000, output_tokens=20_000, reset_at=date.today()
    )

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["spend_usd"] == 0.60
    assert body["over_threshold"] is True
    assert body["threshold_usd"] == 0.50


def test_under_threshold_flag_is_false(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
) -> None:
    admin = user_factory(role="admin")
    # Tiny usage — nowhere near the $10 default.
    _seed_usage(db, admin, input_tokens=1000, output_tokens=500, reset_at=date.today())

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["over_threshold"] is False


def test_excludes_users_whose_counters_are_stale(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """A user whose token_budget_reset_at is yesterday (or earlier) hasn't
    chatted today — their counter still holds a prior day's total and
    must NOT be summed into today's spend."""
    admin = user_factory(role="admin")
    stale = user_factory(email="stale@test.fake")
    fresh = user_factory(email="fresh@test.fake")

    yesterday = date.today() - timedelta(days=1)
    _seed_usage(
        db, stale, input_tokens=500_000, output_tokens=500_000, reset_at=yesterday
    )
    _seed_usage(
        db, fresh, input_tokens=100_000, output_tokens=100_000, reset_at=date.today()
    )

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["input_tokens"] == 100_000  # only fresh@ included
    assert body["output_tokens"] == 100_000
    assert body["users_counted"] == 1


def test_zero_usage_returns_zero_spend(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """No user has chatted today. Endpoint must return zeros, not 500."""
    admin = user_factory(role="admin")

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["input_tokens"] == 0
    assert body["output_tokens"] == 0
    assert body["spend_usd"] == 0.0
    assert body["users_counted"] == 0
    assert body["over_threshold"] is False


def test_backfill_via_date_param(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """?date=YYYY-MM-DD lets an admin backfill a summary for any past day
    whose counters haven't been overwritten yet."""
    admin = user_factory(role="admin")
    target = date(2026, 4, 20)
    _seed_usage(db, admin, input_tokens=10_000, output_tokens=5_000, reset_at=target)

    resp = client.get(
        "/api/admin/cost-summary",
        headers=_bearer(admin),
        params={"date": target.isoformat()},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["date"] == target.isoformat()
    assert body["input_tokens"] == 10_000


# ---------------------------------------------------------------------------
# Structured log line (Cloud Monitoring alert policy feeds off this)
# ---------------------------------------------------------------------------


def test_emits_cost_summary_log_record(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    caplog,
) -> None:
    admin = user_factory(role="admin")
    _seed_usage(
        db, admin, input_tokens=500_000, output_tokens=100_000, reset_at=date.today()
    )

    with caplog.at_level(logging.INFO, logger="app.admin_cost"):
        resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200

    matching = [r for r in caplog.records if r.getMessage() == "cost_summary"]
    assert len(matching) == 1
    r = matching[0]
    assert r.event == "cost_summary"
    assert r.input_tokens == 500_000
    assert r.output_tokens == 100_000
    assert r.model == "claude-sonnet-4-6"
    # Spend = 500k * 3/1M + 100k * 15/1M = $1.50 + $1.50 = $3.00
    assert r.spend_usd == 3.0
    assert r.over_threshold is False


# ---------------------------------------------------------------------------
# Phase 3 Slice 0 — voice spend rollup
# ---------------------------------------------------------------------------


def test_voice_spend_is_summed_and_added_to_total(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Voice rows for today add to total_spend_usd; LLM and voice are
    reported separately in the response shape."""
    from datetime import datetime, timezone

    from app.models import VoiceUsage

    admin = user_factory(role="admin")
    today = date.today()
    _seed_usage(db, admin, input_tokens=100_000, output_tokens=20_000, reset_at=today)
    # 100k * 3/1M + 20k * 15/1M = $0.30 + $0.30 = $0.60 LLM spend.

    db.add_all(
        [
            VoiceUsage(
                user_id=admin.id,
                ts=datetime.now(timezone.utc),
                mode="stt",
                provider="google_chirp",
                model_id="chirp_2",
                duration_sec=30.0,
                cost_usd=0.012,  # 30s @ $0.024/min
            ),
            VoiceUsage(
                user_id=admin.id,
                ts=datetime.now(timezone.utc),
                mode="stt",
                provider="google_chirp",
                model_id="chirp_2",
                duration_sec=60.0,
                cost_usd=0.024,
            ),
        ]
    )
    db.commit()

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["spend_usd"] == 0.6
    assert payload["voice_spend_usd"] == 0.036
    assert payload["total_spend_usd"] == 0.636


def test_voice_spend_from_other_days_is_not_counted(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """Yesterday's voice rows must not show up in today's total."""
    from datetime import datetime, timedelta, timezone

    from app.models import VoiceUsage

    admin = user_factory(role="admin")
    today = date.today()
    _seed_usage(db, admin, input_tokens=0, output_tokens=0, reset_at=today)

    yesterday_ts = datetime.now(timezone.utc) - timedelta(days=1)
    db.add(
        VoiceUsage(
            user_id=admin.id,
            ts=yesterday_ts,
            mode="stt",
            provider="google_chirp",
            model_id="chirp_2",
            duration_sec=120.0,
            cost_usd=0.048,
        )
    )
    db.commit()

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["voice_spend_usd"] == 0.0
    assert payload["total_spend_usd"] == 0.0


def test_voice_spend_alone_can_trip_threshold(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    """A voice-heavy day with zero LLM spend should still alert if
    total_spend_usd crosses the threshold."""
    from datetime import datetime, timezone

    from app.models import VoiceUsage

    settings = get_settings()
    threshold = settings.daily_cost_alert_threshold_usd

    admin = user_factory(role="admin")
    today = date.today()
    _seed_usage(db, admin, input_tokens=0, output_tokens=0, reset_at=today)

    db.add(
        VoiceUsage(
            user_id=admin.id,
            ts=datetime.now(timezone.utc),
            mode="stt",
            provider="google_chirp",
            model_id="chirp_2",
            duration_sec=10000.0,
            cost_usd=float(threshold) + 0.10,
        )
    )
    db.commit()

    resp = client.get("/api/admin/cost-summary", headers=_bearer(admin))
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["spend_usd"] == 0.0
    assert payload["voice_spend_usd"] > threshold
    assert payload["over_threshold"] is True
