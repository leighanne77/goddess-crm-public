"""Symmetric encryption for Google OAuth tokens stored on the User row.

Fernet (AES-128-CBC + HMAC-SHA256) over the token_encryption_key setting.
The same key encrypts and decrypts; rotation means re-encrypting every
row with a fresh key (see runbook — out of scope for this slice).

Plaintext fallback: when the key is empty (dev convenience), encrypt
and decrypt are pass-throughs. Enterprise mode rejects an empty key at
startup (see app.config), so this fallback never triggers in prod.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_FERNET_PREFIX = "gAAAAA"


def _fernet() -> Fernet | None:
    key = get_settings().token_encryption_key
    if not key:
        return None
    return Fernet(key.encode())


def looks_encrypted(value: str) -> bool:
    """Heuristic: Fernet tokens are url-safe base64 starting with 'gAAAAA'."""
    return value.startswith(_FERNET_PREFIX)


def encrypt(plaintext: str) -> str:
    f = _fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    f = _fernet()
    if f is None:
        return ciphertext
    if not looks_encrypted(ciphertext):
        # Pre-migration plaintext still in the column. Return as-is so
        # callers keep working until the data migration runs.
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Failed to decrypt token — key mismatch or corrupted ciphertext."
        ) from exc
