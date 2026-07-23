"""Audit logging decorator for write endpoints.

Usage:
    @audit_log(action="create_contact", target_type="contact")
    def create_contact(payload, db, current_user) -> Contact:
        ...

After the route function returns successfully, an audit_log row is
written. Inputs we hash but do not store verbatim (privacy + size).

If audit logging fails for any reason, we log the error but don't fail
the user's request — audit infrastructure should never break the app.
"""

import functools
import hashlib
import inspect
import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.services import agent_context

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def hash_payload(payload: Any) -> str | None:
    """Return a SHA-256 hex of the canonical JSON of the payload, or None."""
    if payload is None:
        return None
    try:
        if hasattr(payload, "model_dump"):
            data = payload.model_dump(mode="json")
        else:
            data = payload
        canonical = json.dumps(data, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_target_id(
    target_id_kwarg: str | None,
    kwargs: dict[str, Any],
    return_value: Any,
) -> int | None:
    """Pull target_id from kwargs by name, falling back to return_value.id."""
    if target_id_kwarg and target_id_kwarg in kwargs:
        value = kwargs[target_id_kwarg]
        if isinstance(value, int):
            return value
    if hasattr(return_value, "id") and isinstance(return_value.id, int):
        return return_value.id
    return None


def write_audit_row(
    db: Session,
    user: User,
    action: str,
    target_type: str | None,
    target_id: int | None,
    payload_hash: str | None,
    payload_metadata: dict[str, Any] | None = None,
) -> None:
    """Persist one audit row. `payload_metadata` (Slice 6.9) is the
    optional action-specific structured payload that powers the
    field-level change log; see the AuditLog model for the per-action
    shape convention. NULL for actions that don't carry diff data
    (e.g. redacted_reveal, share_contact)."""
    # Stamp the acting agent + policy version into every row written
    # inside an agent scope (app/services/agent_context). Explicit
    # metadata keys win on collision — the stamp never clobbers.
    stamp = agent_context.current()
    if stamp:
        payload_metadata = {**stamp, **(payload_metadata or {})}
    try:
        db.add(
            AuditLog(
                user_id=user.id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                payload_hash=payload_hash,
                payload_metadata=payload_metadata,
            )
        )
        db.commit()
    except Exception:
        logger.exception("audit_log write failed for action=%s", action)
        db.rollback()


def audit_log(
    *,
    action: str,
    target_type: str | None = None,
    target_id_kwarg: str | None = None,
    payload_kwarg: str | None = "payload",
) -> Callable[[F], F]:
    """Decorator that records a write event after the wrapped function returns.

    target_id_kwarg: which kwarg holds the target id (e.g. "contact_id").
        If absent or None, falls back to the return value's `.id`.
    payload_kwarg: which kwarg holds the request body to hash. Default "payload".
    """

    def decorator(func: F) -> F:
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await func(*args, **kwargs)
                _record(
                    action, target_type, target_id_kwarg, payload_kwarg, kwargs, result
                )
                return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            _record(action, target_type, target_id_kwarg, payload_kwarg, kwargs, result)
            return result

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _record(
    action: str,
    target_type: str | None,
    target_id_kwarg: str | None,
    payload_kwarg: str | None,
    kwargs: dict[str, Any],
    result: Any,
) -> None:
    user = kwargs.get("current_user")
    db = kwargs.get("db")
    if not isinstance(user, User) or not isinstance(db, Session):
        logger.warning(
            "audit_log skipped for action=%s — missing current_user or db kwarg",
            action,
        )
        return
    target_id = _resolve_target_id(target_id_kwarg, kwargs, result)
    payload = kwargs.get(payload_kwarg) if payload_kwarg else None
    payload_hash = hash_payload(payload)
    write_audit_row(db, user, action, target_type, target_id, payload_hash)
