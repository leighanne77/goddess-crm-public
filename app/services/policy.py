"""Policy engine v1 — the shared rulebook reader (harness slice 1).

Reads app/policies.yaml (the policy layer: guardrails as DATA) and
answers one question: may agent X call tool Y right now?

    evaluate("dess-chat", "delete_contact") -> PolicyDecision(CONFIRM, ...)

Design rules (the DESS agent-harness pattern):
  - Deny-by-default: a tool not listed for the agent is DENIED.
  - Fail-closed: if the policy file is missing or unparseable, EVERYTHING
    is denied (reason=policy_unavailable). An unreachable rulebook means
    NO, not YES.
  - Shadow mode first: the dispatcher logs the verdict on every call; it
    only *enforces* when POLICY_ENFORCE=true (config). This lets us watch
    the engine agree with reality before flipping it live.
  - CONFIRM means "requires human confirmation." Server-side confirm
    tokens are harness slice 2 — until then, enforce-mode treats CONFIRM
    as allow-with-loud-log (the model-level confirm rule P-07 still
    applies in the prompt).

No LLM anywhere in here — the trust path stays deterministic (P-11).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

POLICY_PATH = Path(__file__).resolve().parent.parent / "policies.yaml"

# Module-level cache: {"policy": dict|None, "loaded": bool}. None after a
# failed load ⇒ every evaluate() fails closed until reset_cache().
_cache: dict[str, Any] = {"policy": None, "loaded": False}


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CONFIRM = "CONFIRM"


@dataclass(frozen=True)
class PolicyDecision:
    verdict: Verdict
    agent_id: str
    tool: str
    reason: str
    policy_version: int | None  # None ⇔ rulebook unavailable (fail-closed)
    # hard=True means the deny applies even in SHADOW mode. Reserved for
    # operator actions like the per-agent kill switch (enabled: false) —
    # a kill switch that only logs isn't a kill switch.
    hard: bool = False


def _load_policy() -> dict[str, Any] | None:
    """Load + cache policies.yaml. Any failure returns None (fail closed)."""
    if _cache["loaded"]:
        return _cache["policy"]  # type: ignore[return-value]
    try:
        with POLICY_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or "agents" not in data:
            raise ValueError("policies.yaml missing required 'agents' mapping")
        _cache["policy"] = data
    except Exception:  # noqa: BLE001 — every load failure fails closed
        logger.exception("policy: failed to load %s — failing CLOSED", POLICY_PATH)
        _cache["policy"] = None
    _cache["loaded"] = True
    return _cache["policy"]  # type: ignore[return-value]


def reset_cache() -> None:
    """Test hook / ops hook: force a re-read on next evaluate()."""
    _cache["policy"] = None
    _cache["loaded"] = False


def current_version() -> int | None:
    """The version of the rulebook in force (None ⇔ unavailable). Used
    to stamp audit rows via agent_context outside the dispatcher."""
    policy = _load_policy()
    return policy.get("version") if policy else None


def evaluate(agent_id: str, tool: str) -> PolicyDecision:
    """May `agent_id` call `tool`? Deny-by-default, fail-closed."""
    policy = _load_policy()
    if policy is None:
        return PolicyDecision(
            Verdict.DENY, agent_id, tool, "policy_unavailable (fail-closed)", None
        )
    version = policy.get("version")
    agent = (policy.get("agents") or {}).get(agent_id)
    if not isinstance(agent, dict):
        return PolicyDecision(
            Verdict.DENY, agent_id, tool, f"unknown agent {agent_id!r}", version
        )
    # Kill switch: enabled defaults to true; an explicit false blocks the
    # agent HARD — shadow mode does not soften an operator's off-switch.
    if agent.get("enabled", True) is False:
        return PolicyDecision(
            Verdict.DENY,
            agent_id,
            tool,
            f"agent {agent_id!r} is disabled (kill switch)",
            version,
            hard=True,
        )
    tools = agent.get("tools") or {}
    if tool in (tools.get("confirm") or []):
        return PolicyDecision(
            Verdict.CONFIRM, agent_id, tool, "listed in confirm", version
        )
    if tool in (tools.get("allow") or []):
        return PolicyDecision(Verdict.ALLOW, agent_id, tool, "listed in allow", version)
    return PolicyDecision(
        Verdict.DENY, agent_id, tool, "not in allowlist (deny-by-default)", version
    )
