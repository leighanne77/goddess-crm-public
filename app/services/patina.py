"""Pydantic schema for user-editable rolodex patina marks.

Background. Each contact card in the CRM can carry a "patina" — a
sticker, pencil note, doodle, or other vintage rolodex flourish. By
default the frontend picks one deterministically from the contact's
ID (no DB state needed). Users can override that pick via voice
commands ("add smiley sticker on Marcus", "remove patina on Diana"),
which writes a list of PatinaItem objects to the `patina_overrides`
JSONB column.

Design (per the Slice 4.5 review):
- Discriminated union on `kind` so Pydantic routes parsing automatically
  (no hand-rolled switch). Idiomatic Pydantic v2 pattern with
  Annotated[Union[...], Field(discriminator="kind")].
- Store INTENT only — kind, text, color, shape. Do NOT store positions
  or rotations; those are derived deterministically at render time
  from (contact.id, item index).
- Cap the list at 3 items via Field(max_length=3) so a card never gets
  visually crowded.

The frontend mirrors these types in client.ts; keep them in sync. A
future code-gen path (pydantic2ts / datamodel-code-generator) is
captured in Future_Ideas.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Catalogs (mirror frontend constants in components/CardPatina.tsx)
# ---------------------------------------------------------------------------

SmudgeInk = Literal["lightGray", "warmGray", "lightBrown", "tanBrown"]
SmudgeShape = Literal["full", "partial", "doubled", "streak", "fingertip"]
DogEarCorner = Literal["top-left", "bottom-left", "bottom-right"]
DoodleShape = Literal["flower", "smiley", "star", "squiggle", "spiral"]
StickerShape = Literal["smiley", "star", "dot"]
TypewrittenColor = Literal[
    "greenish",
    "darkRed",
    "darkBlue",
    "gray",
    "lightBrown",
    "tanBrown",
]

# 9-zone grid for user-specified patina placement. Voice grammar maps
# "lower right" -> "bottom-right", "upper left" -> "top-left", etc.
# When omitted, the renderer picks a deterministic position from
# (contact.id, item index) so cards always look stable.
PatinaPosition = Literal[
    "top-left",
    "top-center",
    "top-right",
    "middle-left",
    "middle-center",
    "middle-right",
    "bottom-left",
    "bottom-center",
    "bottom-right",
]


# ---------------------------------------------------------------------------
# Patina items — each is its own model united by Literal["kind"] so Pydantic
# can route parsing automatically via Field(discriminator="kind").
# ---------------------------------------------------------------------------


class SmudgeItem(BaseModel):
    """Hand-oil smudge — soft blurred ellipse, no ridge lines."""

    kind: Literal["smudge"]
    ink: SmudgeInk = "lightGray"
    shape: SmudgeShape = "full"
    position: PatinaPosition | None = None


class DogEarItem(BaseModel):
    """Folded corner of the card."""

    kind: Literal["dogear"]
    corner: DogEarCorner = "bottom-right"


class PencilNoteItem(BaseModel):
    """Handwritten pencil note in Caveat font."""

    kind: Literal["pencilNote"]
    text: str = Field(..., min_length=1, max_length=40)
    position: PatinaPosition | None = None


class DoodleItem(BaseModel):
    """Pencil doodle — flower, smiley, star, squiggle, spiral."""

    kind: Literal["doodle"]
    shape: DoodleShape
    position: PatinaPosition | None = None


PencilSymbol = Literal["check", "hash", "question", "caret"]


class CheckMarkItem(BaseModel):
    """Quick hand-drawn pencil mark — a check, hash (#), question (?),
    or caret (^). The kind name is "check" for backward compatibility
    with earlier data; the symbol field is what actually drives the
    visual."""

    kind: Literal["check"]
    symbol: PencilSymbol = "check"
    position: PatinaPosition | None = None


class TypewrittenItem(BaseModel):
    """Typewritten text in a vintage ribbon color."""

    kind: Literal["typewritten"]
    text: str = Field(..., min_length=1, max_length=40)
    color: TypewrittenColor = "gray"
    position: PatinaPosition | None = None


class MailingLabelItem(BaseModel):
    """White mailing-label sticker with typewritten text."""

    kind: Literal["mailingLabel"]
    text: str = Field(..., min_length=1, max_length=30)
    position: PatinaPosition | None = None


class StickerItem(BaseModel):
    """Decorative sticker — smiley, star, or colored dot."""

    kind: Literal["sticker"]
    shape: StickerShape = "smiley"
    # Hex color, e.g. "#E8A82A". Defaults vary per shape; the frontend
    # supplies a sensible default if missing.
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    position: PatinaPosition | None = None


PatinaItem = Annotated[
    Union[
        SmudgeItem,
        DogEarItem,
        PencilNoteItem,
        DoodleItem,
        CheckMarkItem,
        TypewrittenItem,
        MailingLabelItem,
        StickerItem,
    ],
    Field(discriminator="kind"),
]
"""Discriminated union of every patina kind. Pydantic uses the `kind`
field to route parsing — no hand-rolled dispatch needed."""


PATINA_OVERRIDES_MAX = 3
"""Cap so a card never gets visually crowded by user-added marks."""


# ---------------------------------------------------------------------------
# Change-request payloads — Phase 2 review queue (Day 5 Slice 5.5)
# ---------------------------------------------------------------------------
#
# A non-owner files a request asking the contact's owner to either:
#   - move the contact to fly_status="Off Fly List"   (kind=off_fly_list)
#   - replace the contact's patina_overrides list      (kind=patina_override)
#
# Discriminator on `kind` matches the same pattern PatinaItem uses.


class OffFlyListPayload(BaseModel):
    """No payload — the kind itself is the request."""

    kind: Literal["off_fly_list"]


class PatinaOverridePayload(BaseModel):
    """Proposed replacement patina list. Same shape the user would set
    via update_contact.patina_overrides, capped at the same max."""

    kind: Literal["patina_override"]
    items: list[PatinaItem] = Field(
        default_factory=list, max_length=PATINA_OVERRIDES_MAX
    )


ChangeRequestPayload = Annotated[
    Union[OffFlyListPayload, PatinaOverridePayload],
    Field(discriminator="kind"),
]
"""Discriminated union routed by `kind`. Pydantic parses the payload
into the right subclass automatically — no hand-rolled dispatch."""
