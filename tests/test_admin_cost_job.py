"""Tests for POST /admin/run-daily-cost-job (Slice 7.1)."""

from __future__ import annotations

from datetime import date
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
    user.daily_input_tokens_used = input_tokens
    user.daily_output_tokens_used = output_tokens
    user.token_budget_reset_at = reset_at
    db.commit()


class _StubSendAlert:
    """Records send_alert calls; returns whatever SendResult was configured."""

    def __init__(self, result):
        self.result = result
        self.calls: list[tuple[str, str, list[str]]] = []

    def __call__(self, subject: str, body: str, recipients: list[str]):
        self.calls.append((subject, body, list(recipients)))
        return self.result


def _install_stub(monkeypatch, *, sent_to=None, failed=None, skipped_reason=None):
    """Patch send_alert in the router module so no real SMTP fires."""
    from app.routers import admin_cost
    from app.services.email import SendResult

    stub = _StubSendAlert(
        SendResult(
            attempted=(skipped_reason is None),
            sent_to=list(sent_to or []),
            failed=dict(failed or {}),
            skipped_reason=skipped_reason,
        )
    )
    monkeypatch.setattr(admin_cost, "send_alert", stub)
    return stub


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def test_member_gets_403(
    client: TestClient, db: Session, user_factory: Callable[..., User]
) -> None:
    member = user_factory(role="member")
    resp = client.post("/api/admin/run-daily-cost-job", headers=_bearer(member))
    assert resp.status_code == 403


def test_unauthenticated_gets_401(client: TestClient) -> None:
    resp = client.post("/api/admin/run-daily-cost-job")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Threshold gating
# ---------------------------------------------------------------------------


def test_under_threshold_skips_email(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    admin = user_factory(role="admin")
    _seed_usage(db, admin, input_tokens=1000, output_tokens=500, reset_at=date.today())
    stub = _install_stub(monkeypatch, sent_to=[admin.email])

    resp = client.post("/api/admin/run-daily-cost-job", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["over_threshold"] is False
    assert body["email_attempted"] is False
    assert body["email_skipped_reason"] == "under_threshold"
    assert stub.calls == []


def test_over_threshold_sends_email(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "daily_cost_alert_threshold_usd", 0.50)
    admin = user_factory(role="admin")
    _seed_usage(
        db, admin, input_tokens=100_000, output_tokens=20_000, reset_at=date.today()
    )
    stub = _install_stub(monkeypatch, sent_to=[admin.email])

    resp = client.post("/api/admin/run-daily-cost-job", headers=_bearer(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["over_threshold"] is True
    assert body["email_attempted"] is True
    assert body["email_sent_to"] == [admin.email]
    assert len(stub.calls) == 1
    subject, _body, recipients = stub.calls[0]
    assert subject.startswith("[DIN] Daily spend over threshold")
    assert recipients == [admin.email]


def test_dry_run_forces_email_under_threshold(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    admin = user_factory(role="admin")
    # Tiny usage — well under default $10 threshold.
    _seed_usage(db, admin, input_tokens=100, output_tokens=50, reset_at=date.today())
    stub = _install_stub(monkeypatch, sent_to=[admin.email])

    resp = client.post(
        "/api/admin/run-daily-cost-job?dry_run=true", headers=_bearer(admin)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["over_threshold"] is False
    assert body["email_attempted"] is True
    assert body["dry_run"] is True
    assert len(stub.calls) == 1
    subject, _body, _recipients = stub.calls[0]
    assert subject.startswith("[DRY RUN]")


# ---------------------------------------------------------------------------
# Recipient resolution
# ---------------------------------------------------------------------------


def test_recipients_resolve_to_all_admins(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    admin1 = user_factory(role="admin", email="alex@test.fake")
    admin2 = user_factory(role="admin", email="other-admin@test.fake")
    user_factory(role="member", email="sam@test.fake")  # excluded
    user_factory(role="member", email="hj@test.fake")  # excluded
    stub = _install_stub(monkeypatch, sent_to=[admin1.email, admin2.email])

    resp = client.post(
        "/api/admin/run-daily-cost-job?dry_run=true", headers=_bearer(admin1)
    )
    assert resp.status_code == 200
    _subject, _body, recipients = stub.calls[0]
    assert set(recipients) == {admin1.email, admin2.email}


def test_recipients_override_wins_over_admin_query(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "cost_alert_recipients_override",
        "smoke@test.fake, another@test.fake",
    )
    admin = user_factory(role="admin", email="alex@test.fake")
    user_factory(role="admin", email="other-admin@test.fake")
    stub = _install_stub(monkeypatch, sent_to=["smoke@test.fake", "another@test.fake"])

    resp = client.post(
        "/api/admin/run-daily-cost-job?dry_run=true", headers=_bearer(admin)
    )
    assert resp.status_code == 200
    _subject, _body, recipients = stub.calls[0]
    assert recipients == ["smoke@test.fake", "another@test.fake"]


# ---------------------------------------------------------------------------
# SMTP not configured (dev / test default)
# ---------------------------------------------------------------------------


def test_skipped_when_smtp_password_unset(
    client: TestClient,
    db: Session,
    user_factory: Callable[..., User],
    monkeypatch,
) -> None:
    """No real SMTP send is attempted in dev. The endpoint records the skip
    and returns success — important so the daily Cloud Scheduler ping in a
    misconfigured environment doesn't page someone with a 500."""
    admin = user_factory(role="admin")
    _seed_usage(db, admin, input_tokens=100, output_tokens=50, reset_at=date.today())
    stub = _install_stub(monkeypatch, skipped_reason="smtp_password_unset")

    resp = client.post(
        "/api/admin/run-daily-cost-job?dry_run=true", headers=_bearer(admin)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_attempted"] is False
    assert body["email_skipped_reason"] == "smtp_password_unset"
    # send_alert was still called (the skip happens inside it)
    assert len(stub.calls) == 1
