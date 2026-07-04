"""Tests for the Claude API wrapper.

Mocks AsyncAnthropic so no real API call is made. Real-Anthropic
verification lives in Slice 9 (manual smoke test).
"""

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import llm


def _fake_response(input_tokens: int = 100, output_tokens: int = 50) -> Any:
    return SimpleNamespace(
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        content=[SimpleNamespace(type="text", text="hello")],
        stop_reason="end_turn",
    )


@pytest.fixture
def mock_create(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    create = AsyncMock(return_value=_fake_response())
    fake_client = MagicMock()
    fake_client.messages.create = create
    monkeypatch.setattr(llm, "_client", lambda: fake_client)
    return create


async def test_call_claude_does_not_send_unknown_beta_headers(
    mock_create: AsyncMock,
) -> None:
    """We removed zero-retention-20250101 (not a real beta); confirm no
    stale headers sneak back in via extra_headers."""
    await llm.call_claude(
        messages=[{"role": "user", "content": "hi"}],
        system="You are helpful.",
    )
    kwargs = mock_create.call_args.kwargs
    assert "extra_headers" not in kwargs or not kwargs["extra_headers"]


async def test_call_claude_wraps_system_with_cache_control(
    mock_create: AsyncMock,
) -> None:
    await llm.call_claude(
        messages=[{"role": "user", "content": "hi"}],
        system="System content.",
    )
    system = mock_create.call_args.kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["type"] == "text"
    assert system[0]["text"] == "System content."
    assert system[0]["cache_control"] == {"type": "ephemeral"}


async def test_call_claude_caches_last_tool(mock_create: AsyncMock) -> None:
    tools = [
        {"name": "tool_a", "description": "A", "input_schema": {}},
        {"name": "tool_b", "description": "B", "input_schema": {}},
    ]
    await llm.call_claude(
        messages=[{"role": "user", "content": "hi"}],
        system="Sys",
        tools=tools,
    )
    sent = mock_create.call_args.kwargs["tools"]
    assert "cache_control" not in sent[0]
    assert sent[-1]["cache_control"] == {"type": "ephemeral"}


async def test_call_claude_uses_adaptive_thinking(
    mock_create: AsyncMock,
) -> None:
    await llm.call_claude(
        messages=[{"role": "user", "content": "hi"}],
        system="sys",
    )
    assert mock_create.call_args.kwargs["thinking"] == {"type": "adaptive"}


async def test_call_claude_invokes_token_callback(
    mock_create: AsyncMock,
) -> None:
    captured: dict[str, int] = {}

    def cb(input_tokens: int, output_tokens: int) -> None:
        captured["input"] = input_tokens
        captured["output"] = output_tokens

    await llm.call_claude(
        messages=[{"role": "user", "content": "hi"}],
        system="sys",
        on_tokens=cb,
    )
    assert captured == {"input": 100, "output": 50}


async def test_call_claude_uses_configured_model(
    mock_create: AsyncMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "chat_model", "claude-haiku-4-5")
    await llm.call_claude(
        messages=[{"role": "user", "content": "hi"}],
        system="sys",
    )
    assert mock_create.call_args.kwargs["model"] == "claude-haiku-4-5"


def test_api_key_scrubber_redacts_keys_in_log_messages(
    caplog: pytest.LogCaptureFixture,
) -> None:
    target = logging.getLogger("anthropic")
    with caplog.at_level(logging.ERROR, logger="anthropic"):
        target.error("Auth failed: sk-ant-api03-secret-key-here")
    assert "sk-ant-api03-secret-key-here" not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_api_key_scrubber_redacts_keys_in_log_args(
    caplog: pytest.LogCaptureFixture,
) -> None:
    target = logging.getLogger("httpx")
    with caplog.at_level(logging.ERROR, logger="httpx"):
        target.error("request failed: %s", "sk-ant-api03-leaked-via-arg")
    assert "sk-ant-api03-leaked-via-arg" not in caplog.text
    assert "[REDACTED]" in caplog.text
