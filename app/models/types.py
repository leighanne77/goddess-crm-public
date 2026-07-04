"""Custom SQLAlchemy column types."""

from typing import Any

from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine import Dialect

from app.services import token_crypto


class EncryptedString(TypeDecorator[str]):
    """Transparently encrypt on write, decrypt on read.

    Stored as a String; the application sees plaintext. Falls back to
    plaintext when token_encryption_key is unset — see token_crypto.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return token_crypto.encrypt(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return token_crypto.decrypt(value)
