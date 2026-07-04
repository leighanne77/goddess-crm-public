"""Tests for the patina discriminated union schema.

Pydantic does the heavy lifting — these tests confirm the routing
works (each kind parses to the right model), invalid kinds raise,
and the field bounds are enforced.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from app.services.patina import PATINA_OVERRIDES_MAX, PatinaItem

PatinaListAdapter = TypeAdapter(list[PatinaItem])


@pytest.mark.parametrize(
    "raw,expected_kind",
    [
        ({"kind": "smudge"}, "smudge"),
        ({"kind": "smudge", "ink": "tanBrown", "shape": "doubled"}, "smudge"),
        ({"kind": "dogear", "corner": "top-left"}, "dogear"),
        ({"kind": "pencilNote", "text": "tell joke"}, "pencilNote"),
        ({"kind": "doodle", "shape": "flower"}, "doodle"),
        ({"kind": "check"}, "check"),
        ({"kind": "typewritten", "text": "Nashville"}, "typewritten"),
        (
            {"kind": "typewritten", "text": "EST 1987", "color": "darkRed"},
            "typewritten",
        ),
        ({"kind": "mailingLabel", "text": "REVISED 1987"}, "mailingLabel"),
        ({"kind": "sticker"}, "sticker"),
        ({"kind": "sticker", "shape": "star", "color": "#E8A82A"}, "sticker"),
    ],
)
def test_each_kind_parses(raw: dict, expected_kind: str) -> None:
    parsed = PatinaListAdapter.validate_python([raw])
    assert parsed[0].kind == expected_kind


def test_unknown_kind_raises() -> None:
    with pytest.raises(ValidationError):
        PatinaListAdapter.validate_python([{"kind": "ufo"}])


def test_doodle_shape_must_be_in_catalog() -> None:
    """'raindrop' is not in our SVG library — must reject."""
    with pytest.raises(ValidationError):
        PatinaListAdapter.validate_python([{"kind": "doodle", "shape": "raindrop"}])


def test_pencil_note_requires_text() -> None:
    with pytest.raises(ValidationError):
        PatinaListAdapter.validate_python([{"kind": "pencilNote"}])


def test_pencil_note_text_length_capped() -> None:
    long_text = "x" * 100
    with pytest.raises(ValidationError):
        PatinaListAdapter.validate_python([{"kind": "pencilNote", "text": long_text}])


def test_sticker_color_must_be_hex_or_omitted() -> None:
    # Valid hex
    PatinaListAdapter.validate_python([{"kind": "sticker", "color": "#C8202F"}])
    # Omitted is fine — frontend defaults
    PatinaListAdapter.validate_python([{"kind": "sticker"}])
    # Invalid string — must reject
    with pytest.raises(ValidationError):
        PatinaListAdapter.validate_python([{"kind": "sticker", "color": "red"}])


def test_max_three_items_enforced_at_field_level() -> None:
    """The cap is on the *field* in CreateContactInput / UpdateContactInput,
    not on PatinaItem itself — but proving the discriminated union accepts
    a list of 4+ items confirms we need that field-level cap."""
    items = [{"kind": "sticker"} for _ in range(5)]
    parsed = PatinaListAdapter.validate_python(items)
    assert len(parsed) == 5  # the union has no cap; the field does


def test_max_constant_matches_design() -> None:
    """Cap is 3 — guard against accidental change."""
    assert PATINA_OVERRIDES_MAX == 3


def test_pencil_in_two_notes_round_trips() -> None:
    """The 'Ghostbusters' + 'ha ha ha' example."""
    raw = [
        {"kind": "pencilNote", "text": "Ghostbusters"},
        {"kind": "pencilNote", "text": "ha ha ha"},
    ]
    parsed = PatinaListAdapter.validate_python(raw)
    assert len(parsed) == 2
    assert all(p.kind == "pencilNote" for p in parsed)
    assert [p.text for p in parsed] == ["Ghostbusters", "ha ha ha"]


def test_position_zone_round_trips_for_sticker() -> None:
    """The 'add smiley sticker on the lower right' example."""
    raw = [
        {"kind": "sticker", "shape": "smiley", "position": "bottom-right"},
    ]
    parsed = PatinaListAdapter.validate_python(raw)
    assert parsed[0].kind == "sticker"
    assert parsed[0].position == "bottom-right"


def test_position_zone_rejects_unknown_value() -> None:
    """'corner-eating' is not a valid zone."""
    with pytest.raises(ValidationError):
        PatinaListAdapter.validate_python(
            [{"kind": "sticker", "position": "corner-eating"}]
        )


def test_position_zone_omitted_is_fine() -> None:
    """Position is optional — frontend derives one when missing."""
    raw = [{"kind": "sticker", "shape": "star"}]
    parsed = PatinaListAdapter.validate_python(raw)
    assert parsed[0].position is None
