"""JWT session token utilities.

create_access_token issues a token. decode_access_token returns the
user_id on success or None on any failure (expired, tampered, malformed,
or missing required claims). Callers should not need to distinguish
failure modes — None means "not authenticated."
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings


def create_access_token(user_id: int) -> str:
    """Sign a JWT with sub=user_id and a configured expiration."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiration_days)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int | None:
    """Verify a JWT signature + expiration. Return the user_id or None."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        return None
    return int(sub)
