"""Server-side confirmation tokens — harness slice 2 (registry P-07).

Two-phase destructive operations: the FIRST tool call (no token) always
fails safe with `confirm_required` + a freshly-issued token; only a
second call carrying that token back performs the action. The server —
not the model's manners — guarantees no single-call delete/transfer.

Stateless by design (Cloud Run runs multiple instances): the token is
`base64url(action:target_id:user_id:extra:expiry) . HMAC(jwt_secret)`,
so any instance can verify what any other issued. 10-minute expiry.
`extra` binds action-specific arguments (e.g. the transfer recipient) so
a token confirmed for one outcome can't authorize a different one.

Remaining gap (tracked in policies.yaml P-07): the confirming "yes"
still travels through the model's conversation. A UI-level confirm
button is the eventual end state; this slice removes the single-call
bypass and makes every confirm auditable (token issue → token use).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from app.config import get_settings

TTL_SECONDS = 600  # 10 minutes — long enough to ask, short enough to die


def _sign(payload: str) -> str:
    secret = get_settings().jwt_secret.encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue(action: str, target_id: int, user_id: int, extra: str = "") -> str:
    """Mint a confirmation token bound to (action, target, user, extra)."""
    expires = int(time.time()) + TTL_SECONDS
    payload = f"{action}:{target_id}:{user_id}:{extra}:{expires}"
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{encoded}.{_sign(payload)}"


def verify(
    token: str, action: str, target_id: int, user_id: int, extra: str = ""
) -> bool:
    """True iff the token is well-formed, unexpired, untampered, and bound
    to exactly this (action, target, user, extra). Any failure → False —
    callers treat False as "issue a fresh token and ask again"."""
    try:
        encoded, sig = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001 — malformed input is just "no"
        return False
    if not hmac.compare_digest(_sign(payload), sig):
        return False
    parts = payload.rsplit(":", 1)
    if len(parts) != 2:
        return False
    body, expires_s = parts
    try:
        if int(expires_s) < time.time():
            return False
    except ValueError:
        return False
    return hmac.compare_digest(body, f"{action}:{target_id}:{user_id}:{extra}")
