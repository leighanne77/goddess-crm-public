"""Claude-generated sheet names for the export endpoint.

Best-effort. Naming should never block an export — if Claude is slow,
returns garbage, or rate-limits, the caller falls back to a
deterministic format. The export itself always succeeds.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date

from app.services import llm

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0
_MAX_LEN = 60
_NEWLINE_RE = re.compile(r"\s+")
_QUOTE_RE = re.compile(r'^[\'"`]+|[\'"`]+$')


def _fallback(filter_summary: str, count: int) -> str:
    """Deterministic name used when Claude can't be reached or returns
    something unusable. Same format the endpoint had before Claude
    naming was added — kept stable so test snapshots and audit-log
    fingerprints remain comparable."""
    label = filter_summary or "All"
    return f"DIN Contacts — {label} — {date.today().isoformat()} ({count})"


def _sanitize(raw: str) -> str:
    """Coerce Claude's reply into something safe to use as a sheet name.

    - Take only the first line (Claude sometimes pads with chatter)
    - Strip surrounding quotes / backticks
    - Collapse internal whitespace
    - Cap at _MAX_LEN
    - Reject anything empty or starting with a code-fence marker
    """
    if not raw:
        return ""
    first_line = raw.split("\n", 1)[0]
    first_line = _QUOTE_RE.sub("", first_line)
    first_line = _NEWLINE_RE.sub(" ", first_line).strip()
    if first_line.startswith("```") or first_line.startswith("#"):
        return ""
    return first_line[:_MAX_LEN]


def _prompt(filter_summary: str, count: int) -> str:
    return (
        "Suggest a concise, descriptive name for a Google Sheet "
        f"containing {count} DIN contacts filtered by: {filter_summary}. "
        "Use 30-50 characters. Include the month/year. Do NOT add "
        "quotes, code fences, or any prose — return ONLY the title text "
        "as a single line. Example: Maritime LP Contacts — April 2026."
    )


async def suggest_name(*, filter_summary: str, count: int) -> str:
    """Ask Claude for a sheet name. Always returns a usable string —
    falls back to the deterministic format on any failure path:
      - timeout > 5s
      - Claude SDK error (rate limit, network, etc.)
      - Claude returns something unusable (empty, code fence)
      - ENTERPRISE_MODE guard fires (won't happen for filter strings,
        but defensive)
    """
    fallback = _fallback(filter_summary, count)
    try:
        response = await asyncio.wait_for(
            llm.call_claude(
                messages=[{"role": "user", "content": _prompt(filter_summary, count)}],
                system=(
                    "You generate short, descriptive titles for Google "
                    "Sheets exports. Single line, no prose, no quotes."
                ),
                tools=None,
                on_tokens=None,
                max_tokens=60,
            ),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.info("sheet name generation timed out; using fallback")
        return fallback
    except Exception:  # noqa: BLE001 — naming failures must never block export
        logger.exception("sheet name generation failed; using fallback")
        return fallback

    # Pull the first text block from Claude's response.
    text_parts = [
        getattr(b, "text", "")
        for b in response.content
        if getattr(b, "type", None) == "text"
    ]
    cleaned = _sanitize(" ".join(text_parts))
    return cleaned or fallback
