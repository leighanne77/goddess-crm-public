"""DIN voice rules — runtime guard for words we don't allow in replies.

DIN's positioning frames waste/risk in financial and operational terms,
not in political/activist terms. The words "carbon", "climate", and
"ESG" carry that activist framing and are banned from Claude's replies
and from any UI copy we generate.

This module is the runtime safety net. The system prompt also tells
Claude not to use these words — this scrubber catches drift.

Substitutions are deliberately context-light because the system prompt
gives Claude the right framing in the first place. Whole-word matches
only (case-insensitive), so "carbonate", "acclimated", and "Cesgo Inc."
pass through untouched.

Scope (per CLAUDE.md): Claude's reply text + any UI copy we generate.
NOT applied to contact notes or company_name — those are factual
descriptors of real people and firms.
"""

import re

_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcarbon\b", re.IGNORECASE), "operational inefficiency"),
    (re.compile(r"\bclimate\b", re.IGNORECASE), "physical risk"),
    (re.compile(r"\besg\b", re.IGNORECASE), "governance"),
]


def scrub_banned_words(text: str) -> str:
    """Replace banned words in text. Idempotent — safe to call twice."""
    for pattern, replacement in _REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def contains_banned_words(text: str) -> bool:
    """True if text contains any banned word — useful for tests/logging."""
    return any(p.search(text) for p, _ in _REPLACEMENTS)
