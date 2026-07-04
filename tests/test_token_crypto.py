"""Tests for Fernet-based token encryption."""

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.services import token_crypto


def test_round_trip() -> None:
    plain = "ya29.fake-access-token-with-some-length-to-it"
    cipher = token_crypto.encrypt(plain)
    assert cipher != plain
    assert token_crypto.looks_encrypted(cipher)
    assert token_crypto.decrypt(cipher) == plain


def test_decrypt_passthrough_for_pre_migration_plaintext() -> None:
    plain = "ya29.legacy-plaintext-value"
    assert not token_crypto.looks_encrypted(plain)
    assert token_crypto.decrypt(plain) == plain


def test_decrypt_with_wrong_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    cipher = token_crypto.encrypt("secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="Failed to decrypt"):
            token_crypto.decrypt(cipher)
    finally:
        get_settings.cache_clear()


def test_passthrough_when_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    try:
        assert token_crypto.encrypt("plain") == "plain"
        assert token_crypto.decrypt("plain") == "plain"
    finally:
        get_settings.cache_clear()


def test_ciphertext_starts_with_fernet_prefix() -> None:
    cipher = token_crypto.encrypt("anything")
    assert cipher.startswith("gAAAAA")


def test_two_encryptions_of_same_plaintext_differ() -> None:
    """Fernet IV is random — same input encrypts to different ciphertexts."""
    a = token_crypto.encrypt("same")
    b = token_crypto.encrypt("same")
    assert a != b
    assert token_crypto.decrypt(a) == token_crypto.decrypt(b) == "same"
