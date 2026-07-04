"""Tests for the sheet-naming service.

Naming is best-effort. The service must:
  - Return Claude's response when it's clean
  - Sanitize gracefully (strip quotes, take first line, cap length)
  - Fall back to deterministic format on timeout / error / garbage
  - NEVER raise — exports must not fail because of naming
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import sheet_naming


def _fake_response(text: str) -> MagicMock:
    """Build the minimum object suggest_name() reads from a Claude reply."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


@pytest.mark.asyncio
async def test_returns_claude_text_when_clean() -> None:
    with patch(
        "app.services.sheet_naming.llm.call_claude",
        new=AsyncMock(return_value=_fake_response("Maritime LP Contacts — April 2026")),
    ):
        name = await sheet_naming.suggest_name(filter_summary="Maritime LP", count=6)
    assert name == "Maritime LP Contacts — April 2026"


@pytest.mark.asyncio
async def test_strips_surrounding_quotes() -> None:
    with patch(
        "app.services.sheet_naming.llm.call_claude",
        new=AsyncMock(return_value=_fake_response('"Saudi Energy LPs — April 2026"')),
    ):
        name = await sheet_naming.suggest_name(filter_summary="x", count=1)
    assert name == "Saudi Energy LPs — April 2026"


@pytest.mark.asyncio
async def test_takes_only_first_line() -> None:
    """Claude sometimes pads with chatter — we use only the first line."""
    with patch(
        "app.services.sheet_naming.llm.call_claude",
        new=AsyncMock(
            return_value=_fake_response(
                "Critical Minerals — April 2026\nLet me know if you'd like another"
            )
        ),
    ):
        name = await sheet_naming.suggest_name(filter_summary="x", count=1)
    assert name == "Critical Minerals — April 2026"


@pytest.mark.asyncio
async def test_caps_at_60_chars() -> None:
    long_reply = "x" * 200
    with patch(
        "app.services.sheet_naming.llm.call_claude",
        new=AsyncMock(return_value=_fake_response(long_reply)),
    ):
        name = await sheet_naming.suggest_name(filter_summary="x", count=1)
    assert len(name) <= 60


@pytest.mark.asyncio
async def test_falls_back_when_claude_returns_code_fence() -> None:
    """A reply starting with ``` is unusable — fall back to deterministic."""
    with patch(
        "app.services.sheet_naming.llm.call_claude",
        new=AsyncMock(return_value=_fake_response("```\nSome name\n```")),
    ):
        name = await sheet_naming.suggest_name(filter_summary="Maritime", count=3)
    assert name.startswith("DIN Contacts —")
    assert "Maritime" in name


@pytest.mark.asyncio
async def test_falls_back_on_empty_response() -> None:
    with patch(
        "app.services.sheet_naming.llm.call_claude",
        new=AsyncMock(return_value=_fake_response("")),
    ):
        name = await sheet_naming.suggest_name(filter_summary="All", count=22)
    assert name.startswith("DIN Contacts —")


@pytest.mark.asyncio
async def test_falls_back_on_timeout() -> None:
    """If Claude takes longer than the timeout, fall back."""

    async def slow_call(*args: object, **kwargs: object) -> object:
        await asyncio.sleep(10)
        return _fake_response("never gets here")

    with (
        patch(
            "app.services.sheet_naming.llm.call_claude",
            new=AsyncMock(side_effect=slow_call),
        ),
        patch.object(sheet_naming, "_TIMEOUT_SECONDS", 0.05),
    ):
        name = await sheet_naming.suggest_name(filter_summary="Energy", count=2)
    assert name.startswith("DIN Contacts —")
    assert "Energy" in name


@pytest.mark.asyncio
async def test_falls_back_on_claude_exception() -> None:
    """SDK errors / network issues / rate limits — naming never raises."""
    with patch(
        "app.services.sheet_naming.llm.call_claude",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        name = await sheet_naming.suggest_name(filter_summary="x", count=1)
    assert name.startswith("DIN Contacts —")


def test_fallback_format_is_stable() -> None:
    """Snapshot for the deterministic format (audit-log fingerprint stability)."""
    result = sheet_naming._fallback("Maritime LP", 6)
    assert result.startswith("DIN Contacts — Maritime LP — ")
    assert result.endswith(" (6)")
