"""Tests for Google ID token verification.

We mint our own RSA keypair, expose its public half as a fake JWKS,
patch the JWKS fetcher to return it, and sign tokens with the private
half. Real Google is never contacted.
"""

import base64
import time
from typing import Any, Callable

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from jose import jwt

from app.config import get_settings
from app.services import google_oauth
from app.services.google_oauth import verify_google_id_token

TEST_KID = "test-kid-1"
TEST_CLIENT_ID = "test-client-id-12345"


def _b64url_uint(value: int) -> str:
    byte_length = (value.bit_length() + 7) // 8
    return (
        base64.urlsafe_b64encode(value.to_bytes(byte_length, "big"))
        .rstrip(b"=")
        .decode()
    )


@pytest.fixture
def rsa_keypair() -> dict[str, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    public_numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "kid": TEST_KID,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url_uint(public_numbers.n),
        "e": _b64url_uint(public_numbers.e),
    }
    return {"private_pem": pem, "jwk": jwk}


@pytest.fixture
def mock_jwks(monkeypatch: pytest.MonkeyPatch, rsa_keypair: dict[str, Any]) -> None:
    google_oauth._jwks_cache["data"] = None

    fake_jwks = {"keys": [rsa_keypair["jwk"]]}

    async def _fake_fetch() -> dict[str, Any]:
        return fake_jwks

    monkeypatch.setattr(google_oauth, "_fetch_jwks", _fake_fetch)


@pytest.fixture
def configured_client_id(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(get_settings(), "google_client_id", TEST_CLIENT_ID)
    return TEST_CLIENT_ID


@pytest.fixture
def signed_token_factory(
    rsa_keypair: dict[str, Any], configured_client_id: str
) -> Callable[..., str]:
    def _make(**overrides: Any) -> str:
        claims = {
            "iss": "https://accounts.google.com",
            "aud": configured_client_id,
            "sub": "google-user-abc",
            "email": "test@example.com",
            "exp": int(time.time()) + 3600,
            **overrides,
        }
        return jwt.encode(
            claims,
            rsa_keypair["private_pem"],
            algorithm="RS256",
            headers={"kid": TEST_KID},
        )

    return _make


async def test_valid_token_returns_claims(
    mock_jwks: None, signed_token_factory: Callable[..., str]
) -> None:
    token = signed_token_factory()
    claims = await verify_google_id_token(token)
    assert claims["email"] == "test@example.com"
    assert claims["sub"] == "google-user-abc"


async def test_tampered_token_raises(
    mock_jwks: None, signed_token_factory: Callable[..., str]
) -> None:
    token = signed_token_factory()
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(ValueError):
        await verify_google_id_token(tampered)


async def test_expired_token_raises(
    mock_jwks: None, signed_token_factory: Callable[..., str]
) -> None:
    token = signed_token_factory(exp=int(time.time()) - 60)
    with pytest.raises(ValueError):
        await verify_google_id_token(token)


async def test_wrong_audience_raises(
    mock_jwks: None, signed_token_factory: Callable[..., str]
) -> None:
    token = signed_token_factory(aud="someone-elses-client-id")
    with pytest.raises(ValueError):
        await verify_google_id_token(token)


async def test_wrong_issuer_raises(
    mock_jwks: None, signed_token_factory: Callable[..., str]
) -> None:
    token = signed_token_factory(iss="https://evil.example.com")
    with pytest.raises(ValueError):
        await verify_google_id_token(token)
