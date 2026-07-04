"""User model stores tokens encrypted, reads them back as plaintext."""

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import User
from app.services import token_crypto


def test_tokens_stored_ciphertext_read_plaintext(
    db: Session, user_factory: Callable[..., User]
) -> None:
    user = user_factory(
        google_access_token="ya29.plaintext-access",
        google_refresh_token="1//plaintext-refresh",
    )
    db.commit()

    # Read raw column values — should be Fernet ciphertext.
    row = db.execute(
        text(
            "SELECT google_access_token, google_refresh_token "
            "FROM users WHERE id = :id"
        ),
        {"id": user.id},
    ).one()
    assert token_crypto.looks_encrypted(row.google_access_token)
    assert token_crypto.looks_encrypted(row.google_refresh_token)
    assert row.google_access_token != "ya29.plaintext-access"

    # Model attribute returns plaintext.
    db.expire(user)
    refreshed = db.get(User, user.id)
    assert refreshed is not None
    assert refreshed.google_access_token == "ya29.plaintext-access"
    assert refreshed.google_refresh_token == "1//plaintext-refresh"


def test_null_tokens_stay_null(db: Session, user_factory: Callable[..., User]) -> None:
    user = user_factory(google_access_token=None, google_refresh_token=None)
    db.commit()
    row = db.execute(
        text(
            "SELECT google_access_token, google_refresh_token "
            "FROM users WHERE id = :id"
        ),
        {"id": user.id},
    ).one()
    assert row.google_access_token is None
    assert row.google_refresh_token is None


def test_legacy_plaintext_row_still_readable(
    db: Session, user_factory: Callable[..., User]
) -> None:
    """Defense in depth: if a plaintext row slipped past the migration,
    the model should still return it (token_crypto.decrypt is back-compat)."""
    user = user_factory(google_access_token=None)
    db.execute(
        text("UPDATE users SET google_access_token = :v WHERE id = :id"),
        {"v": "ya29.raw-plaintext", "id": user.id},
    )
    db.commit()
    db.expire_all()
    refreshed = db.get(User, user.id)
    assert refreshed is not None
    assert refreshed.google_access_token == "ya29.raw-plaintext"
