"""Confirm tokens (harness slice 2, P-07) — the server-side two-step.

The token is the whole guarantee: bound to (action, target, user, extra),
HMAC-signed, 10-minute expiry. Anything off by one field is a "no".
"""

import time

from app.services import confirm_tokens
from app.services.confirm_tokens import issue, verify


def test_round_trip_verifies() -> None:
    t = issue("delete_contact", 42, 7)
    assert verify(t, "delete_contact", 42, 7) is True


def test_bound_to_action_target_user() -> None:
    t = issue("delete_contact", 42, 7)
    assert verify(t, "transfer_contact", 42, 7) is False  # other action
    assert verify(t, "delete_contact", 43, 7) is False  # other contact
    assert verify(t, "delete_contact", 42, 8) is False  # other user


def test_transfer_token_binds_recipient() -> None:
    """Confirming a transfer to Ellen can't authorize one to anyone else."""
    t = issue("transfer_contact", 42, 7, extra="ellen@x.fake")
    assert verify(t, "transfer_contact", 42, 7, extra="ellen@x.fake") is True
    assert verify(t, "transfer_contact", 42, 7, extra="hj@x.fake") is False
    assert verify(t, "transfer_contact", 42, 7) is False


def test_expired_token_fails(monkeypatch) -> None:
    t = issue("delete_contact", 42, 7)
    future = time.time() + confirm_tokens.TTL_SECONDS + 5
    monkeypatch.setattr(confirm_tokens.time, "time", lambda: future)
    assert verify(t, "delete_contact", 42, 7) is False


def test_tampered_token_fails() -> None:
    t = issue("delete_contact", 42, 7)
    encoded, sig = t.split(".", 1)
    assert verify(f"{encoded}.{'0' * len(sig)}", "delete_contact", 42, 7) is False
    assert verify("garbage", "delete_contact", 42, 7) is False
    assert verify("", "delete_contact", 42, 7) is False
