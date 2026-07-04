"""Tests for app.security and the Settings JWT-secret validator."""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.security import create_access_token, decode_access_token


def test_token_round_trip_returns_user_id() -> None:
    token = create_access_token(user_id=42)
    assert decode_access_token(token) == 42


def test_expired_token_returns_none() -> None:
    settings = get_settings()
    expired_payload = {
        "sub": "42",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    expired_token = jwt.encode(
        expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    assert decode_access_token(expired_token) is None


def test_tampered_token_returns_none() -> None:
    token = create_access_token(user_id=42)
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert decode_access_token(tampered) is None


def test_settings_rejects_default_jwt_secret_in_enterprise_mode() -> None:
    with pytest.raises(ValidationError):
        Settings(enterprise_mode=True, jwt_secret="change-me")


def test_settings_allows_default_jwt_secret_outside_enterprise_mode() -> None:
    settings = Settings(enterprise_mode=False, jwt_secret="change-me")
    assert settings.jwt_secret == "change-me"


def test_settings_requires_token_encryption_key_in_enterprise_mode() -> None:
    with pytest.raises(ValidationError, match="token_encryption_key"):
        Settings(
            enterprise_mode=True,
            jwt_secret="not-the-default-value-here",
            token_encryption_key="",
        )


def test_settings_allows_empty_token_encryption_key_outside_enterprise_mode() -> None:
    settings = Settings(enterprise_mode=False, token_encryption_key="")
    assert settings.token_encryption_key == ""
