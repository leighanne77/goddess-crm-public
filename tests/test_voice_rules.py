"""Tests for the DIN voice-rules scrubber.

The scrubber is the runtime safety net for words the system prompt also
forbids. These tests prove the rule covers obvious cases and doesn't
fire on innocent substrings.
"""

import pytest

from app.services.voice_rules import contains_banned_words, scrub_banned_words


@pytest.mark.parametrize(
    "input_text,expected",
    [
        # Whole-word matches get substituted
        ("Carbon emissions are high", "operational inefficiency emissions are high"),
        ("CARBON drag", "operational inefficiency drag"),
        ("climate risk", "physical risk risk"),  # naive but acceptable
        ("Climate change", "physical risk change"),
        ("ESG-aligned investors", "governance-aligned investors"),
        ("esg disclosure", "governance disclosure"),
    ],
)
def test_scrubber_replaces_whole_words(input_text: str, expected: str) -> None:
    assert scrub_banned_words(input_text) == expected


@pytest.mark.parametrize(
    "innocent",
    [
        "carbonate compounds",  # 'carbon' substring
        "acclimated to the role",  # 'climate' substring
        "Cesgo Inc.",  # 'esg' substring
        "Carbondale, IL",  # 'carbon' substring in proper noun
    ],
)
def test_scrubber_leaves_innocent_substrings_alone(innocent: str) -> None:
    assert scrub_banned_words(innocent) == innocent
    assert not contains_banned_words(innocent)


def test_scrubber_is_idempotent() -> None:
    text = "Carbon and climate and ESG all in one"
    once = scrub_banned_words(text)
    twice = scrub_banned_words(once)
    assert once == twice


def test_contains_banned_words_detects_each() -> None:
    assert contains_banned_words("carbon")
    assert contains_banned_words("CLIMATE")
    assert contains_banned_words("Esg")
    assert not contains_banned_words("everything is fine here")
