"""Day 3 Slice 0 — verify safety-rail settings load with sane defaults
and that the User model has the new token-budget columns."""

from typing import Callable

from sqlalchemy import inspect

from app.config import Settings
from app.database import engine
from app.models import User


def test_settings_have_safe_default_caps() -> None:
    settings = Settings()
    assert settings.chat_input_max_chars == 4000
    assert settings.chat_rate_limit_per_hour == 60
    assert settings.chat_input_token_budget_per_day == 500_000
    assert settings.chat_output_token_budget_per_day == 125_000
    assert settings.chat_tool_iteration_cap == 5
    assert settings.chat_history_max_turns == 20


def test_users_table_has_token_budget_columns() -> None:
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("users")}
    assert "daily_input_tokens_used" in columns
    assert "daily_output_tokens_used" in columns
    assert "token_budget_reset_at" in columns
    assert "daily_input_token_budget_override" in columns
    assert "rate_limit_per_hour_override" in columns


def test_new_user_starts_with_zero_token_usage_and_no_overrides(
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    assert user.daily_input_tokens_used == 0
    assert user.daily_output_tokens_used == 0
    assert user.token_budget_reset_at is None
    assert user.daily_input_token_budget_override is None
    assert user.rate_limit_per_hour_override is None
