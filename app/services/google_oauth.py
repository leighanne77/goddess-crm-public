"""Google ID token verification.

Google signs every ID token with one of a small set of rotating RSA
keys. We fetch the public keys from Google's JWKS endpoint, cache them
for an hour, then verify the token's signature, audience (must be our
client id), expiration, and issuer.

verify_google_id_token raises ValueError on any failure so callers can
treat any failure mode the same way: reject the login.
"""

import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.config import get_settings

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
JWKS_CACHE_TTL_SECONDS = 3600

_jwks_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}


async def _fetch_jwks() -> dict[str, Any]:
    """Return Google's JWKS, refreshing once an hour."""
    now = time.monotonic()
    cached = _jwks_cache["data"]
    if cached is not None and now - _jwks_cache["fetched_at"] < JWKS_CACHE_TTL_SECONDS:
        return cached
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(GOOGLE_JWKS_URL)
        resp.raise_for_status()
        data = resp.json()
    _jwks_cache["data"] = data
    _jwks_cache["fetched_at"] = now
    return data


async def verify_google_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Google-issued ID token. Return its claims or raise ValueError."""
    settings = get_settings()
    if not settings.google_client_id:
        raise ValueError("google_client_id is not configured")

    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as e:
        raise ValueError(f"Malformed token header: {e}") from e
    kid = header.get("kid")
    if not kid:
        raise ValueError("Token missing kid header")

    jwks = await _fetch_jwks()
    matching_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if matching_key is None:
        raise ValueError(f"No matching JWK for kid={kid}")

    try:
        claims = jwt.decode(
            id_token,
            matching_key,
            algorithms=[header.get("alg", "RS256")],
            audience=settings.google_client_id,
            options={"verify_iss": False, "verify_at_hash": False},
        )
    except JWTError as e:
        raise ValueError(f"Token verification failed: {e}") from e

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise ValueError(f"Bad issuer: {claims.get('iss')}")

    return claims
