"""Ambient agent identity — harness slice 3.

Which agent is acting right now? The dispatcher (and any agent-owned
router, e.g. Satchel's) sets this for the duration of one operation;
`write_audit_row` reads it and stamps `agent_id` + `policy_version`
into every audit row written underneath — all 20+ call sites get
attribution without threading a parameter through each handler.

ContextVar, not a global: safe under async concurrency — each request's
context is isolated, so two simultaneous requests can't cross-stamp.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_current: ContextVar[dict[str, Any] | None] = ContextVar(
    "din_agent_context", default=None
)


def set_agent(agent_id: str, policy_version: int | None) -> Token:
    """Enter an agent scope. Returns the token for `clear()` (use
    try/finally so an exception never leaks identity into later work)."""
    return _current.set({"agent_id": agent_id, "policy_version": policy_version})


def clear(token: Token) -> None:
    _current.reset(token)


def deactivate() -> None:
    """Exit an agent scope WITHOUT a token. For FastAPI dependency
    teardown, which may resume in a different context than the set()
    (token reset would raise 'created in a different Context' there).
    Sets the var to None in the current context instead."""
    _current.set(None)


def current() -> dict[str, Any] | None:
    """The acting agent's stamp, or None outside any agent scope
    (e.g. plain REST endpoints a human drives directly)."""
    return _current.get()
