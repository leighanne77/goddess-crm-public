/**
 * Patina marks for ContactCard. Each card picks deterministically from
 * the slot table by `contact.id`, so any given person always carries
 * the same mark, but the variety across the rolodex is rich.
 *
 * Slot layout (60 slots total):
 *   0-39    one of 8 patina categories (40 unique variants)
 *   40-59   no patina (20 nulls)
 * That's ~67% coverage, layered on top of the stain layer (~30%), so
 * roughly 80% of cards carry SOME mark.
 *
 * Design rules:
 *   - One patina element per card max — never two patina marks layered
 *   - Every position is unique across slots (no two cards share placement)
 *   - Marks must NOT obscure name, gold rule, or fund/type pills
 *   - The airplane corner (top-right) is reserved — no patina there
 */

type Position = {
  // CSS positioning. At least one anchor is set per element.
  top?: string;
  right?: string;
  bottom?: string;
  left?: string;
};

type SmudgeInk = "lightGray" | "warmGray" | "lightBrown" | "tanBrown";
/** Five smudge shapes — full pad, partial, doubled, streak, fingertip. */
type SmudgeVariant = 0 | 1 | 2 | 3 | 4;
type SmudgePatina = {
  kind: "smudge";
  pos: Position;
  rotate: number;
  ink: SmudgeInk;
  variant: SmudgeVariant;
};
type DogEarPatina = {
  kind: "dogear";
  corner: "top-left" | "bottom-left" | "bottom-right";
  size: number;
};
type PencilNotePatina = {
  kind: "pencilNote";
  text: string;
  pos: Position;
  rotate: number;
};
type DoodlePatina = {
  kind: "doodle";
  shape: "flower" | "smiley" | "star" | "squiggle" | "spiral";
  pos: Position;
  rotate: number;
  size: number;
};
type PencilSymbol = "check" | "hash" | "question" | "caret";
type CheckPatina = {
  kind: "check";
  /** Defaults to "check" for backward compat. Hash/question/caret are
   *  the same hand-drawn pencil look, different symbol. */
  symbol?: PencilSymbol;
  pos: Position;
  rotate: number;
  size: number;
};
type TypewrittenPatina = {
  kind: "typewritten";
  text: string;
  color: string;
  pos: Position;
  rotate: number;
};
type MailingLabelPatina = {
  kind: "mailingLabel";
  text: string;
  pos: Position;
  rotate: number;
};
type StickerPatina = {
  kind: "sticker";
  shape: "smiley" | "star" | "dot";
  color: string;
  pos: Position;
  size: number;
  rotate: number;
};

type CornerTearPatina = {
  kind: "cornerTear";
  /** Top-right reserved for the airplane badge — only three corners. */
  corner: "top-left" | "bottom-left" | "bottom-right";
  /** Tiny ~14px or medium ~22px bite. */
  size: "tiny" | "medium";
};

/** Pen marks — everything from a sharp ballpoint dot to an accidental
 *  sharpie smudge. `tip` differentiates the look of dots and streaks:
 *  ballpoint is small and crisp, felt is slightly larger with a soft
 *  bleed halo. `sharpie` is a dedicated shape (wider felt marker). */
type PenMarkPatina = {
  kind: "penMark";
  shape: "dot" | "streak" | "sharpie";
  /** Ignored for shape=sharpie (sharpie is always felt). */
  tip?: "ballpoint" | "felt";
  color: string; // hex like "#1A3A8A"
  pos: Position;
  rotate: number;
};

export type Patina =
  | SmudgePatina
  | DogEarPatina
  | PencilNotePatina
  | DoodlePatina
  | CheckPatina
  | TypewrittenPatina
  | MailingLabelPatina
  | StickerPatina
  | CornerTearPatina
  | PenMarkPatina;

export const PATINA_SLOTS: (Patina | null)[] = [
  // ---------- Fingerprints (8 entries — 5 ridge patterns × 4 inks ×
  // varied left-edge positions, several partial/off-the-edge per the
  // real handling pattern) ----------
  {
    // Loop pattern, partial top-left edge
    kind: "smudge",
    pos: { top: "18%", left: "-14px" },
    rotate: -8,
    ink: "lightGray",
    variant: 0,
  },
  {
    // Whorl pattern, mid-left, fully visible
    kind: "smudge",
    pos: { top: "44%", left: "4%" },
    rotate: 12,
    ink: "lightBrown",
    variant: 1,
  },
  {
    // Arch pattern, partial bottom-left edge
    kind: "smudge",
    pos: { bottom: "22%", left: "-12px" },
    rotate: -22,
    ink: "warmGray",
    variant: 2,
  },
  {
    // Loop pattern again, but tan ink and upper-left
    kind: "smudge",
    pos: { top: "28%", left: "10%" },
    rotate: 5,
    ink: "tanBrown",
    variant: 0,
  },
  {
    // Tented arch, lower-left, partial off-edge
    kind: "smudge",
    pos: { bottom: "8%", left: "-10px" },
    rotate: 16,
    ink: "lightGray",
    variant: 3,
  },
  {
    // Double loop, mid-left, fully visible
    kind: "smudge",
    pos: { top: "55%", left: "8%" },
    rotate: -14,
    ink: "lightBrown",
    variant: 4,
  },
  {
    // Whorl, top-left, partial off-edge
    kind: "smudge",
    pos: { top: "8%", left: "-8px" },
    rotate: 4,
    ink: "tanBrown",
    variant: 1,
  },
  {
    // Arch, mid-left, fully visible
    kind: "smudge",
    pos: { top: "36%", left: "2%" },
    rotate: 22,
    ink: "warmGray",
    variant: 2,
  },
  // Three upper-right-quadrant smudges, biased to fingerprint-pad shapes
  // (variants 0, 3, 4) so they read like real prints rather than blobs.
  // Positioned to clear the airplane badge at top-right.
  {
    kind: "smudge",
    pos: { top: "8%", right: "-10px" },
    rotate: 18,
    ink: "warmGray",
    variant: 0, // full pad — most print-shaped
  },
  {
    kind: "smudge",
    pos: { top: "26%", right: "8%" },
    rotate: -14,
    ink: "lightBrown",
    variant: 4, // fingertip — small, oval, just-the-tip
  },
  {
    kind: "smudge",
    pos: { top: "18%", right: "-6px" },
    rotate: 28,
    ink: "tanBrown",
    variant: 3, // streak — elongated like a finger drag
  },

  // ---------- Dog-ear folds (3 corners, 2 sizes = 6 variants) ----------
  { kind: "dogear", corner: "top-left", size: 22 },
  { kind: "dogear", corner: "top-left", size: 30 },
  { kind: "dogear", corner: "bottom-left", size: 24 },
  { kind: "dogear", corner: "bottom-left", size: 32 },
  { kind: "dogear", corner: "bottom-right", size: 22 },
  { kind: "dogear", corner: "bottom-right", size: 28 },

  // ---------- Pencil notes (6 text variants, varied positions) ----------
  {
    kind: "pencilNote",
    text: "tell joke",
    pos: { bottom: "26%", right: "8%" },
    rotate: -8,
  },
  {
    kind: "pencilNote",
    text: "follow up",
    pos: { bottom: "12%", left: "20%" },
    rotate: 6,
  },
  {
    kind: "pencilNote",
    text: "more.",
    pos: { top: "55%", right: "10%" },
    rotate: 12,
  },
  {
    kind: "pencilNote",
    text: "great mtg",
    pos: { bottom: "22%", left: "55%" },
    rotate: -4,
  },
  {
    kind: "pencilNote",
    text: "Nov 14",
    pos: { top: "40%", left: "12%" },
    rotate: 3,
  },
  {
    kind: "pencilNote",
    text: "?",
    pos: { top: "50%", right: "20%" },
    rotate: 18,
  },

  // ---------- Doodles (5 shapes, varied positions) ----------
  {
    kind: "doodle",
    shape: "flower",
    pos: { bottom: "28%", right: "16%" },
    rotate: 0,
    size: 22,
  },
  {
    kind: "doodle",
    shape: "smiley",
    pos: { top: "48%", right: "8%" },
    rotate: -10,
    size: 18,
  },
  {
    kind: "doodle",
    shape: "star",
    pos: { bottom: "16%", left: "8%" },
    rotate: 15,
    size: 18,
  },
  {
    kind: "doodle",
    shape: "squiggle",
    pos: { top: "52%", left: "8%" },
    rotate: 0,
    size: 28,
  },
  {
    kind: "doodle",
    shape: "spiral",
    pos: { bottom: "20%", right: "30%" },
    rotate: 0,
    size: 20,
  },

  // ---------- Pencil check marks (4 variants — right/center biased so
  // they don't collide with fingerprint positions on the left) ----------
  // Pencil marks — check / hash / question / caret. Same hand-drawn
  // pencil look across all four; symbol differentiates the visual.
  {
    kind: "check",
    symbol: "check",
    pos: { top: "14%", right: "14%" },
    rotate: -8,
    size: 22,
  },
  {
    kind: "check",
    symbol: "check",
    pos: { bottom: "22%", right: "8%" },
    rotate: 5,
    size: 26,
  },
  {
    kind: "check",
    symbol: "check",
    pos: { top: "46%", right: "22%" },
    rotate: 12,
    size: 20,
  },
  {
    kind: "check",
    symbol: "check",
    pos: { bottom: "14%", right: "32%" },
    rotate: -3,
    size: 18,
  },
  {
    kind: "check",
    symbol: "hash",
    pos: { top: "30%", right: "12%" },
    rotate: 4,
    size: 18,
  },
  {
    kind: "check",
    symbol: "hash",
    pos: { bottom: "30%", right: "20%" },
    rotate: -10,
    size: 16,
  },
  {
    kind: "check",
    symbol: "question",
    pos: { top: "20%", right: "26%" },
    rotate: 8,
    size: 22,
  },
  {
    kind: "check",
    symbol: "question",
    pos: { bottom: "18%", right: "44%" },
    rotate: -5,
    size: 20,
  },
  {
    kind: "check",
    symbol: "caret",
    pos: { top: "38%", right: "38%" },
    rotate: 0,
    size: 18,
  },
  {
    kind: "check",
    symbol: "caret",
    pos: { bottom: "32%", right: "12%" },
    rotate: 6,
    size: 16,
  },

  // ---------- Typewritten dates (6 ink colors / positions) ----------
  // Vintage typewriter ribbons came in these colors.
  {
    kind: "typewritten",
    text: "EST. 1987",
    color: "rgba(40, 80, 50, 0.55)", // greenish
    pos: { bottom: "8%", right: "10%" },
    rotate: -2,
  },
  {
    kind: "typewritten",
    text: "MET 03/14/91",
    color: "rgba(110, 30, 30, 0.55)", // dark red
    pos: { top: "44%", right: "8%" },
    rotate: 1,
  },
  {
    kind: "typewritten",
    text: "REF: 4421",
    color: "rgba(30, 50, 90, 0.55)", // dark blue
    pos: { bottom: "8%", left: "10%" },
    rotate: -3,
  },
  {
    kind: "typewritten",
    text: "RECD 1979",
    color: "rgba(60, 60, 60, 0.55)", // gray
    pos: { top: "52%", left: "10%" },
    rotate: 4,
  },
  {
    kind: "typewritten",
    text: "FILE 22-A",
    color: "rgba(110, 75, 40, 0.55)", // light brown
    pos: { bottom: "16%", right: "30%" },
    rotate: -1,
  },
  {
    kind: "typewritten",
    text: "VERIFIED",
    color: "rgba(140, 90, 50, 0.50)", // lighter brown
    pos: { top: "20%", left: "44%" },
    rotate: 2,
  },
  {
    kind: "typewritten",
    text: "TLA",
    color: "rgba(60, 60, 60, 0.55)", // gray
    pos: { bottom: "10%", left: "40%" },
    rotate: -3,
  },
  {
    kind: "typewritten",
    text: "AUSTIN",
    color: "rgba(40, 80, 50, 0.55)", // greenish
    pos: { top: "30%", left: "30%" },
    rotate: 1,
  },
  {
    kind: "typewritten",
    text: "NYC",
    color: "rgba(110, 30, 30, 0.55)", // dark red
    pos: { bottom: "26%", right: "32%" },
    rotate: -4,
  },

  // ---------- Mailing labels (4 variants — rare, evocative) ----------
  {
    kind: "mailingLabel",
    text: "REVISED 1987",
    pos: { bottom: "30%", right: "6%" },
    rotate: 3,
  },
  {
    kind: "mailingLabel",
    text: "SEE FUN NOTE",
    pos: { top: "44%", left: "6%" },
    rotate: -4,
  },
  {
    kind: "mailingLabel",
    text: "RAS 02/95",
    pos: { bottom: "18%", left: "30%" },
    rotate: 2,
  },
  {
    kind: "mailingLabel",
    text: "UPDATED 12/02",
    pos: { top: "52%", right: "6%" },
    rotate: -2,
  },

  // ---------- Stickers (5 variants) ----------
  {
    kind: "sticker",
    shape: "smiley",
    color: "#F0BB52", // gold-soft, faded gold sticker
    pos: { top: "40%", right: "8%" },
    size: 18,
    rotate: 8,
  },
  {
    kind: "sticker",
    shape: "star",
    color: "#E8A82A", // gold star
    pos: { bottom: "18%", right: "12%" },
    size: 16,
    rotate: -10,
  },
  {
    kind: "sticker",
    shape: "dot",
    color: "#C8202F", // red priority dot
    pos: { top: "16%", left: "10%" },
    size: 12,
    rotate: 0,
  },
  {
    kind: "sticker",
    shape: "dot",
    color: "#4A6B8A", // blue category dot
    pos: { bottom: "20%", left: "12%" },
    size: 12,
    rotate: 0,
  },
  {
    kind: "sticker",
    shape: "smiley",
    color: "#E8A82A",
    pos: { bottom: "30%", left: "60%" },
    size: 16,
    rotate: -5,
  },

  // ---------- Pen marks (20 variants — ballpoint + felt dots in a
  // full pen-color palette, a few streaks, and three sharpie smudges)
  // Ballpoint dots: crisp, small
  {
    kind: "penMark",
    shape: "dot",
    tip: "ballpoint",
    color: "#1A3A8A",
    pos: { top: "32%", right: "30%" },
    rotate: 0,
  }, // navy blue
  {
    kind: "penMark",
    shape: "dot",
    tip: "ballpoint",
    color: "#0F0F0F",
    pos: { bottom: "26%", left: "44%" },
    rotate: 0,
  }, // black
  {
    kind: "penMark",
    shape: "dot",
    tip: "ballpoint",
    color: "#A82020",
    pos: { top: "60%", right: "26%" },
    rotate: 0,
  }, // red
  {
    kind: "penMark",
    shape: "dot",
    tip: "ballpoint",
    color: "#0E5230",
    pos: { bottom: "12%", right: "44%" },
    rotate: 0,
  }, // dark green
  {
    kind: "penMark",
    shape: "dot",
    tip: "ballpoint",
    color: "#1B6E4F",
    pos: { top: "24%", left: "40%" },
    rotate: 0,
  }, // emerald green
  {
    kind: "penMark",
    shape: "dot",
    tip: "ballpoint",
    color: "#5A2575",
    pos: { bottom: "22%", right: "58%" },
    rotate: 0,
  }, // purple
  {
    kind: "penMark",
    shape: "dot",
    tip: "ballpoint",
    color: "#C46A1A",
    pos: { top: "66%", left: "48%" },
    rotate: 0,
  }, // orange
  // Felt dots: slightly bigger, softer edges (bleed halo)
  {
    kind: "penMark",
    shape: "dot",
    tip: "felt",
    color: "#1F8B8B",
    pos: { top: "44%", right: "34%" },
    rotate: 0,
  }, // teal felt
  {
    kind: "penMark",
    shape: "dot",
    tip: "felt",
    color: "#4E6E2E",
    pos: { bottom: "32%", left: "56%" },
    rotate: 0,
  }, // olive-green felt
  {
    kind: "penMark",
    shape: "dot",
    tip: "felt",
    color: "#6B3A1C",
    pos: { top: "20%", right: "46%" },
    rotate: 0,
  }, // brown felt
  {
    kind: "penMark",
    shape: "dot",
    tip: "felt",
    color: "#B02888",
    pos: { top: "54%", left: "18%" },
    rotate: 0,
  }, // magenta felt
  {
    kind: "penMark",
    shape: "dot",
    tip: "felt",
    color: "#0F0F0F",
    pos: { bottom: "18%", right: "12%" },
    rotate: 0,
  }, // black felt
  // Streaks — mix of ballpoint (tight) and felt (wider)
  {
    kind: "penMark",
    shape: "streak",
    tip: "ballpoint",
    color: "#1A3A8A",
    pos: { top: "50%", left: "30%" },
    rotate: -8,
  }, // blue ballpoint squiggle
  {
    kind: "penMark",
    shape: "streak",
    tip: "ballpoint",
    color: "#0F0F0F",
    pos: { bottom: "30%", right: "20%" },
    rotate: 12,
  }, // black ballpoint scribble
  {
    kind: "penMark",
    shape: "streak",
    tip: "felt",
    color: "#0E5230",
    pos: { top: "40%", left: "54%" },
    rotate: -4,
  }, // green felt streak
  {
    kind: "penMark",
    shape: "streak",
    tip: "felt",
    color: "#A82020",
    pos: { bottom: "40%", left: "24%" },
    rotate: 10,
  }, // red felt streak
  // Sharpie smudges — wider, blurred, distinctive "accidental brush" marks
  {
    kind: "penMark",
    shape: "sharpie",
    color: "#0a0a0a",
    pos: { bottom: "20%", left: "32%" },
    rotate: 18,
  }, // black sharpie
  {
    kind: "penMark",
    shape: "sharpie",
    color: "#3a1a1a",
    pos: { top: "44%", right: "12%" },
    rotate: -22,
  }, // dark-red sharpie
  {
    kind: "penMark",
    shape: "sharpie",
    color: "#0c2a18",
    pos: { bottom: "12%", left: "10%" },
    rotate: 14,
  }, // dark-green sharpie
  {
    kind: "penMark",
    shape: "sharpie",
    color: "#1a1a3a",
    pos: { top: "14%", left: "42%" },
    rotate: -8,
  }, // dark-blue sharpie

  // ---------- Corner tears (5 variants — different corners and sizes,
  // skipping top-right where the airplane lives) ----------
  { kind: "cornerTear", corner: "bottom-left", size: "tiny" },
  { kind: "cornerTear", corner: "bottom-left", size: "medium" },
  { kind: "cornerTear", corner: "bottom-right", size: "tiny" },
  { kind: "cornerTear", corner: "bottom-right", size: "medium" },
  { kind: "cornerTear", corner: "top-left", size: "tiny" },

  // ---------- 20 null slots — these cards get no patina ----------
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
];

export function pickPatina(id: number): Patina | null {
  return PATINA_SLOTS[id % PATINA_SLOTS.length];
}

// ---------------------------------------------------------------------------
// User-override translation
// ---------------------------------------------------------------------------

/**
 * Loose payload mirroring the backend Pydantic schema. We accept missing
 * fields and fall back to defaults; if a payload is genuinely malformed
 * we return null and skip rendering rather than crash the card.
 */
type OverridePayload = {
  kind: string;
  ink?: string;
  shape?: string;
  corner?: string;
  text?: string;
  color?: string | null;
  position?: string | null;
  symbol?: string;
};

/**
 * 9-zone grid → CSS Position. Voice grammar maps "lower right" to
 * "bottom-right" etc. When the user supplies a position on a sticker /
 * doodle / pencil-note / etc., we convert here. Each zone keeps a small
 * inset from the edge so marks don't crash into the corner radius.
 */
const POSITION_ZONES: Record<string, Position> = {
  "top-left": { top: "8%", left: "8%" },
  "top-center": { top: "8%", left: "44%" },
  "top-right": { top: "8%", right: "8%" },
  "middle-left": { top: "44%", left: "8%" },
  "middle-center": { top: "44%", left: "44%" },
  "middle-right": { top: "44%", right: "8%" },
  "bottom-left": { bottom: "16%", left: "8%" },
  "bottom-center": { bottom: "16%", left: "44%" },
  "bottom-right": { bottom: "16%", right: "8%" },
};

const SMUDGE_INKS_LIST: SmudgeInk[] = [
  "lightGray",
  "warmGray",
  "lightBrown",
  "tanBrown",
];

const DOG_EAR_CORNERS: DogEarPatina["corner"][] = [
  "top-left",
  "bottom-left",
  "bottom-right",
];

const DOODLE_SHAPES: DoodlePatina["shape"][] = [
  "flower",
  "smiley",
  "star",
  "squiggle",
  "spiral",
];

const STICKER_SHAPES: StickerPatina["shape"][] = ["smiley", "star", "dot"];

const TYPEWRITTEN_COLOR_MAP: Record<string, string> = {
  greenish: "rgba(40, 80, 50, 0.55)",
  darkRed: "rgba(110, 30, 30, 0.55)",
  darkBlue: "rgba(30, 50, 90, 0.55)",
  gray: "rgba(60, 60, 60, 0.55)",
  lightBrown: "rgba(110, 75, 40, 0.55)",
  tanBrown: "rgba(140, 90, 50, 0.50)",
};

/**
 * Layout buckets — when the user adds 1-3 patina items, place each in
 * a distinct safe zone so they don't pile up. Position derived from
 * (contact.id, item index), so the same contact + item combo always
 * looks the same.
 */
const OVERRIDE_POSITIONS: Position[] = [
  { top: "30%", left: "8%" },
  { bottom: "20%", right: "10%" },
  { top: "55%", left: "55%" },
];

function pickRotate(seed: number, index: number): number {
  // Deterministic pseudo-random rotation in [-15, 15], unique per slot.
  const v = (seed * 31 + index * 7) % 30;
  return v - 15;
}

function inkFor(seed: number): SmudgeInk {
  return SMUDGE_INKS_LIST[seed % SMUDGE_INKS_LIST.length];
}

/**
 * Translate a single override payload into a renderable Patina, with
 * deterministic position and rotation derived from contact id + index.
 * Returns null on malformed payload (defensive — frontend never crashes
 * on bad data).
 */
export function patinaFromOverride(
  payload: OverridePayload,
  contactId: number,
  index: number,
): Patina | null {
  // User-supplied position wins; otherwise derive deterministically by
  // (contact.id, item index) from the OVERRIDE_POSITIONS bucket.
  const pos: Position =
    (payload.position && POSITION_ZONES[payload.position]) ||
    OVERRIDE_POSITIONS[index] ||
    OVERRIDE_POSITIONS[0];
  const rotate = pickRotate(contactId, index);
  const seed = contactId + index;

  switch (payload.kind) {
    case "smudge":
      return {
        kind: "smudge",
        pos,
        rotate,
        ink:
          (payload.ink as SmudgeInk | undefined) &&
          SMUDGE_INKS_LIST.includes(payload.ink as SmudgeInk)
            ? (payload.ink as SmudgeInk)
            : inkFor(seed),
        variant: (seed % 5) as SmudgeVariant,
      };
    case "dogear": {
      const corner =
        (payload.corner as DogEarPatina["corner"] | undefined) &&
        DOG_EAR_CORNERS.includes(payload.corner as DogEarPatina["corner"])
          ? (payload.corner as DogEarPatina["corner"])
          : DOG_EAR_CORNERS[seed % DOG_EAR_CORNERS.length];
      return { kind: "dogear", corner, size: 24 + (seed % 8) };
    }
    case "pencilNote":
      if (!payload.text) return null;
      return { kind: "pencilNote", text: payload.text, pos, rotate };
    case "doodle": {
      if (
        !payload.shape ||
        !DOODLE_SHAPES.includes(payload.shape as DoodlePatina["shape"])
      ) {
        return null;
      }
      return {
        kind: "doodle",
        shape: payload.shape as DoodlePatina["shape"],
        pos,
        rotate,
        size: 22,
      };
    }
    case "check": {
      // Voice grammar maps "add a question mark on Marcus" -> kind=check,
      // symbol=question. Default to "check" for backward compat.
      const symbol = (payload.symbol as PencilSymbol | undefined) || "check";
      const validSymbols: PencilSymbol[] = [
        "check",
        "hash",
        "question",
        "caret",
      ];
      return {
        kind: "check",
        symbol: validSymbols.includes(symbol) ? symbol : "check",
        pos,
        rotate,
        size: 22,
      };
    }
    case "typewritten":
      if (!payload.text) return null;
      return {
        kind: "typewritten",
        text: payload.text,
        color:
          TYPEWRITTEN_COLOR_MAP[payload.color ?? "gray"] ??
          TYPEWRITTEN_COLOR_MAP.gray,
        pos,
        rotate,
      };
    case "mailingLabel":
      if (!payload.text) return null;
      return { kind: "mailingLabel", text: payload.text, pos, rotate };
    case "sticker": {
      const shape =
        (payload.shape as StickerPatina["shape"] | undefined) &&
        STICKER_SHAPES.includes(payload.shape as StickerPatina["shape"])
          ? (payload.shape as StickerPatina["shape"])
          : "smiley";
      const color = payload.color ?? "#E8A82A"; // gold default
      return { kind: "sticker", shape, color, pos, size: 18, rotate };
    }
    default:
      return null;
  }
}

/**
 * Fly-status drives auto-pick patina DENSITY — more patina on contacts
 * the team actually uses, less on abandoned ones. Deterministic per id
 * (same roll uses `id % 100`).
 *
 *   Must Fly       → always 1 mark + 60% chance of a second (heavy use)
 *   Fly List       → 90% chance of 1 mark (regular use)
 *   Maybe Must Fly → 50% chance of 1 mark (under review, occasional use)
 *   Unknown        → 25% chance of 1 mark (new / undecided contact)
 *   Off Fly List   → no patina (abandoned card)
 *
 * User-customized patina (patina_overrides != null) bypasses density —
 * the user's explicit intent beats fly-status heuristics.
 *
 * Slice 6.11 — "Not Sure Yet" kept as a legacy key so any pre-migration
 * rows still in flight hit the same density as Maybe Must Fly.
 */
const FLY_DENSITY: Record<string, { primary: number; secondary: number }> = {
  "Must Fly": { primary: 100, secondary: 60 },
  "Fly List": { primary: 90, secondary: 0 },
  "Maybe Must Fly": { primary: 50, secondary: 0 },
  "Not Sure Yet": { primary: 50, secondary: 0 },
  Unknown: { primary: 25, secondary: 0 },
  "Off Fly List": { primary: 0, secondary: 0 },
};

/**
 * Pick the patina list to render for a contact:
 *   - patina_overrides == null  → auto-pick, density scaled by fly_status
 *   - patina_overrides == []    → no patina at all
 *   - patina_overrides == [...] → render each override
 */
export function patinaForContact(
  contactId: number,
  overrides: OverridePayload[] | null | undefined,
  flyStatus?: string,
): Patina[] {
  if (overrides === null || overrides === undefined) {
    const density = FLY_DENSITY[flyStatus ?? "Unknown"] ?? {
      primary: 67,
      secondary: 0,
    };
    const roll = contactId % 100;
    const items: Patina[] = [];
    if (roll < density.primary) {
      const first = pickPatina(contactId);
      if (first) items.push(first);
    }
    // Must Fly gets a shot at a second mark, picked from a different
    // slot offset so it doesn't land where the first one did.
    if (density.secondary > 0) {
      const secondRoll = (contactId * 7 + 13) % 100;
      if (secondRoll < density.secondary) {
        const second = pickPatina(contactId * 3 + 11);
        if (second && second !== items[0]) items.push(second);
      }
    }
    return items;
  }
  return overrides
    .map((p, i) => patinaFromOverride(p, contactId, i))
    .filter((p): p is Patina => p !== null);
}

// ---------------------------------------------------------------------------
// Renderers
// ---------------------------------------------------------------------------

interface CardPatinaProps {
  patina: Patina;
}

export function CardPatina({ patina }: CardPatinaProps) {
  switch (patina.kind) {
    case "smudge":
      return (
        <Smudge
          pos={patina.pos}
          rotate={patina.rotate}
          ink={patina.ink}
          variant={patina.variant}
        />
      );
    case "dogear":
      return <DogEar corner={patina.corner} size={patina.size} />;
    case "pencilNote":
      return (
        <PencilNote
          text={patina.text}
          pos={patina.pos}
          rotate={patina.rotate}
        />
      );
    case "doodle":
      return (
        <Doodle
          shape={patina.shape}
          pos={patina.pos}
          rotate={patina.rotate}
          size={patina.size}
        />
      );
    case "check":
      return (
        <CheckMark
          pos={patina.pos}
          rotate={patina.rotate}
          size={patina.size}
          symbol={patina.symbol}
        />
      );
    case "typewritten":
      return (
        <Typewritten
          text={patina.text}
          color={patina.color}
          pos={patina.pos}
          rotate={patina.rotate}
        />
      );
    case "mailingLabel":
      return (
        <MailingLabel
          text={patina.text}
          pos={patina.pos}
          rotate={patina.rotate}
        />
      );
    case "sticker":
      return (
        <Sticker
          shape={patina.shape}
          color={patina.color}
          pos={patina.pos}
          size={patina.size}
          rotate={patina.rotate}
        />
      );
    case "cornerTear":
      return <CornerTear corner={patina.corner} size={patina.size} />;
    case "penMark":
      return (
        <PenMark
          shape={patina.shape}
          tip={patina.tip}
          color={patina.color}
          pos={patina.pos}
          rotate={patina.rotate}
        />
      );
  }
}

/**
 * Hand-oil smudge. Soft, irregular, with feathered edges. No ridge lines —
 * just blurred organic blobs in light grays and tans. Each variant is a
 * composition of overlapping ellipses that, when blurred, produce a
 * naturally uneven smudge shape. Some are partial (one side faded) so
 * positioned-off-the-edge slots show the smudge running off the card.
 */
const SMUDGE_INKS: Record<SmudgeInk, string> = {
  lightGray: "rgba(120, 120, 120, 0.55)",
  // Lightened — was reading too dark on cream cards.
  warmGray: "rgba(170, 165, 155, 0.40)",
  lightBrown: "rgba(150, 120, 90, 0.50)",
  tanBrown: "rgba(170, 140, 105, 0.45)",
};

type SmudgeShape = {
  /** Ellipses composed inside a 60×60 viewBox. */
  ellipses: { cx: number; cy: number; rx: number; ry: number; o: number }[];
  /** Gaussian blur stdDev — higher = softer edges. */
  blur: number;
};

const SMUDGE_VARIANTS: SmudgeShape[] = [
  // 0 — Full pad. Two overlapping ellipses for an organic oval.
  {
    blur: 3,
    ellipses: [
      { cx: 30, cy: 30, rx: 18, ry: 22, o: 0.7 },
      { cx: 32, cy: 26, rx: 14, ry: 16, o: 0.5 },
    ],
  },
  // 1 — Partial. Asymmetric blob, fades hard on one side.
  {
    blur: 4,
    ellipses: [
      { cx: 28, cy: 30, rx: 20, ry: 18, o: 0.6 },
      { cx: 38, cy: 26, rx: 8, ry: 10, o: 0.35 },
      { cx: 22, cy: 36, rx: 6, ry: 7, o: 0.3 },
    ],
  },
  // 2 — Doubled. Two distinct touches, like two fingertips.
  {
    blur: 3,
    ellipses: [
      { cx: 22, cy: 26, rx: 12, ry: 14, o: 0.55 },
      { cx: 40, cy: 32, rx: 10, ry: 13, o: 0.5 },
    ],
  },
  // 3 — Streak. Elongated, like a finger drag.
  {
    blur: 4,
    ellipses: [
      { cx: 30, cy: 28, rx: 24, ry: 9, o: 0.55 },
      { cx: 22, cy: 30, rx: 8, ry: 6, o: 0.4 },
      { cx: 38, cy: 26, rx: 6, ry: 5, o: 0.3 },
    ],
  },
  // 4 — Light fingertip. Small, soft, just the tip.
  {
    blur: 3,
    ellipses: [
      { cx: 30, cy: 28, rx: 11, ry: 13, o: 0.5 },
      { cx: 32, cy: 24, rx: 6, ry: 7, o: 0.35 },
    ],
  },
];

function Smudge({
  pos,
  rotate,
  ink,
  variant,
}: {
  pos: Position;
  rotate: number;
  ink: SmudgeInk;
  variant: SmudgeVariant;
}) {
  const color = SMUDGE_INKS[ink];
  const shape = SMUDGE_VARIANTS[variant];
  // Stable filter id per variant so blur is shared across renders.
  const filterId = `smudge-blur-${variant}`;
  // Middle-row smudges (top: 44%) sit near the card's visual center
  // without running off an edge — no natural fade, and multiple
  // opacity attempts (40, 10) still read as a stain rather than
  // wear. Skip rendering entirely for middle positions; top/bottom-
  // row smudges are fine because their edge-overflow softens them.
  if (pos.top === "44%") {
    return null;
  }
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute opacity-70 mix-blend-multiply"
      style={{ ...pos, transform: `rotate(${rotate}deg)` }}
    >
      <svg width="48" height="48" viewBox="0 0 60 60" fill="none">
        <defs>
          <filter id={filterId} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation={shape.blur} />
          </filter>
        </defs>
        <g filter={`url(#${filterId})`}>
          {shape.ellipses.map((e, i) => (
            <ellipse
              key={i}
              cx={e.cx}
              cy={e.cy}
              rx={e.rx}
              ry={e.ry}
              fill={color}
              opacity={e.o}
            />
          ))}
        </g>
      </svg>
    </div>
  );
}

function DogEar({
  corner,
  size,
}: {
  corner: "top-left" | "bottom-left" | "bottom-right";
  size: number;
}) {
  // Each corner has its own clip-path triangle and crease angle.
  const cornerStyle: Record<typeof corner, React.CSSProperties> = {
    "top-left": {
      top: 0,
      left: 0,
      borderTop: `${size}px solid rgba(74, 107, 138, 0.18)`,
      borderRight: `${size}px solid transparent`,
    },
    "bottom-left": {
      bottom: 0,
      left: 0,
      borderBottom: `${size}px solid rgba(74, 107, 138, 0.18)`,
      borderRight: `${size}px solid transparent`,
    },
    "bottom-right": {
      bottom: 0,
      right: 0,
      borderBottom: `${size}px solid rgba(74, 107, 138, 0.18)`,
      borderLeft: `${size}px solid transparent`,
    },
  };
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute h-0 w-0"
      style={cornerStyle[corner]}
    />
  );
}

function PencilNote({
  text,
  pos,
  rotate,
}: {
  text: string;
  pos: Position;
  rotate: number;
}) {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute select-none text-[15px] leading-none text-din-navy/60"
      style={{
        ...pos,
        transform: `rotate(${rotate}deg)`,
        fontFamily: "'Caveat', cursive",
        fontWeight: 500,
      }}
    >
      {text}
    </span>
  );
}

function Doodle({
  shape,
  pos,
  rotate,
  size,
}: {
  shape: "flower" | "smiley" | "star" | "squiggle" | "spiral";
  pos: Position;
  rotate: number;
  size: number;
}) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute text-din-navy/45"
      style={{ ...pos, transform: `rotate(${rotate}deg)` }}
    >
      {shape === "flower" ? (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          {/* 6-petal flower made of overlapping circles around a center */}
          {[0, 60, 120, 180, 240, 300].map((angle) => {
            const r = (angle * Math.PI) / 180;
            const cx = 12 + Math.cos(r) * 5;
            const cy = 12 + Math.sin(r) * 5;
            return (
              <circle
                key={angle}
                cx={cx}
                cy={cy}
                r="3.5"
                stroke="currentColor"
                strokeWidth="1"
                fill="none"
              />
            );
          })}
          <circle cx="12" cy="12" r="2" fill="currentColor" />
        </svg>
      ) : null}
      {shape === "smiley" ? (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <circle
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="1.2"
            fill="none"
          />
          <circle cx="9" cy="10" r="1" fill="currentColor" />
          <circle cx="15" cy="10" r="1" fill="currentColor" />
          <path
            d="M8 14 Q12 18 16 14"
            stroke="currentColor"
            strokeWidth="1.2"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      ) : null}
      {shape === "star" ? (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <path
            d="M12 2 L14.5 9.5 L22 9.5 L16 14 L18.5 22 L12 17 L5.5 22 L8 14 L2 9.5 L9.5 9.5 Z"
            stroke="currentColor"
            strokeWidth="1"
            fill="none"
          />
        </svg>
      ) : null}
      {shape === "squiggle" ? (
        <svg width={size} height={size / 2} viewBox="0 0 32 16" fill="none">
          <path
            d="M2 8 Q6 2 10 8 T18 8 T26 8 T30 8"
            stroke="currentColor"
            strokeWidth="1.2"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      ) : null}
      {shape === "spiral" ? (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
          <path
            d="M12 12 m -1 0 a 1 1 0 1 0 2 0 a 1 1 0 1 0 -2 0
               M12 12 m -3 0 a 3 3 0 1 1 6 -1
               M12 12 m -5 -1 a 5 5 0 1 1 10 -2
               M12 12 m -7 -2 a 7 7 0 1 1 14 -3"
            stroke="currentColor"
            strokeWidth="1"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      ) : null}
    </div>
  );
}

/**
 * Pencil check mark — drawn faintly, like someone marked the card
 * lightly and then half-erased it. Each instance picks one of three
 * uneven hand-drawn paths (Q-curves with slight wobbles) so no two
 * checks are mechanically identical. Opacity ~22% on top of the very
 * thin stroke gives the "erased pencil" feel.
 */
/** SVG paths per pencil symbol. Each entry is a list of strokes
 *  (multi-stroke symbols like the hash use multiple paths). All paths
 *  use 24x24 viewBox with hand-drawn wobbles so no two are identical.
 */
const PENCIL_SYMBOL_PATHS: Record<PencilSymbol, string[]> = {
  check: [
    // Variant A — leg slightly short, peak overshoots a touch
    "M3 12 Q5.5 14.5 8.5 19 Q11 21 12 19.5 Q15 14 21 4.5",
  ],
  hash: [
    // Two horizontals + two verticals, slightly wobbly hand-drawn lines
    "M3 9 Q12 8 21 9.5",
    "M3 16 Q12 15 21 16.5",
    "M9 3 Q8.5 12 9.5 21",
    "M16 3 Q15.5 12 16.5 21",
  ],
  question: [
    // Curved hook + dot below
    "M7 7 Q9 3 13 4 Q18 5 17 9 Q16 12 13 14 Q12 15 12 17",
    "M12 20 L12.5 20.5",
  ],
  caret: [
    // Up-pointing chevron
    "M5 16 Q11 7 12 6 Q13 7 19 16",
  ],
};

function CheckMark({
  pos,
  rotate,
  size,
  symbol = "check",
}: {
  pos: Position;
  rotate: number;
  size: number;
  symbol?: PencilSymbol;
}) {
  const paths = PENCIL_SYMBOL_PATHS[symbol] ?? PENCIL_SYMBOL_PATHS.check;
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute text-din-navy/30 mix-blend-multiply"
      style={{ ...pos, transform: `rotate(${rotate}deg)` }}
    >
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
        {/* "Erased ghost" stroke layer — broader, lower opacity */}
        {paths.map((d, i) => (
          <path
            key={`g${i}`}
            d={d}
            stroke="currentColor"
            strokeWidth="2.6"
            opacity="0.35"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
        {/* Pencil line on top — thinner, slightly stronger */}
        {paths.map((d, i) => (
          <path
            key={`p${i}`}
            d={d}
            stroke="currentColor"
            strokeWidth="1.1"
            opacity="0.7"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
      </svg>
    </div>
  );
}

function Typewritten({
  text,
  color,
  pos,
  rotate,
}: {
  text: string;
  color: string;
  pos: Position;
  rotate: number;
}) {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute select-none text-[10px] font-bold uppercase tracking-wider"
      style={{
        ...pos,
        color,
        transform: `rotate(${rotate}deg)`,
        fontFamily: "'Courier New', Courier, monospace",
      }}
    >
      {text}
    </span>
  );
}

function MailingLabel({
  text,
  pos,
  rotate,
}: {
  text: string;
  pos: Position;
  rotate: number;
}) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute select-none rounded-[1px] border border-din-navy/15 bg-white px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-din-navy/70 shadow-sm"
      style={{
        ...pos,
        transform: `rotate(${rotate}deg)`,
        fontFamily: "'Courier New', Courier, monospace",
      }}
    >
      {text}
    </div>
  );
}

function Sticker({
  shape,
  color,
  pos,
  size,
  rotate,
}: {
  shape: "smiley" | "star" | "dot";
  color: string;
  pos: Position;
  size: number;
  rotate: number;
}) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute drop-shadow-sm"
      style={{ ...pos, transform: `rotate(${rotate}deg)` }}
    >
      {shape === "smiley" ? (
        <svg width={size} height={size} viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="11" fill={color} />
          <circle cx="9" cy="10" r="1.2" fill="rgba(0,0,0,0.7)" />
          <circle cx="15" cy="10" r="1.2" fill="rgba(0,0,0,0.7)" />
          <path
            d="M8 14 Q12 18 16 14"
            stroke="rgba(0,0,0,0.7)"
            strokeWidth="1.4"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      ) : null}
      {shape === "star" ? (
        <svg width={size} height={size} viewBox="0 0 24 24">
          <path
            d="M12 2 L14.5 9.5 L22 9.5 L16 14 L18.5 22 L12 17 L5.5 22 L8 14 L2 9.5 L9.5 9.5 Z"
            fill={color}
            stroke="rgba(0,0,0,0.25)"
            strokeWidth="0.5"
          />
        </svg>
      ) : null}
      {shape === "dot" ? (
        <svg width={size} height={size} viewBox="0 0 24 24">
          <circle
            cx="12"
            cy="12"
            r="11"
            fill={color}
            stroke="rgba(0,0,0,0.2)"
            strokeWidth="0.5"
          />
        </svg>
      ) : null}
    </div>
  );
}

/**
 * Corner tear — a missing piece of the card. Implementation matches the
 * Off Fly List ripped-channel trick: SVG filled with the page background
 * color, sized 0 to ~22px, with an irregular jagged inner edge so it
 * reads as a torn-off chunk rather than a clean cut.
 *
 * Top-right corner is reserved for the airplane badge — only top-left,
 * bottom-left, and bottom-right are valid.
 */
function CornerTear({
  corner,
  size,
}: {
  corner: "top-left" | "bottom-left" | "bottom-right";
  size: "tiny" | "medium";
}) {
  const px = size === "tiny" ? 14 : 22;
  // Base path is for top-left orientation. The torn edge runs from
  // (px, 0) down through jagged points to (0, px). Inside is "missing."
  const basePath = `M0,0 L${px},0 L${px - 1},2 L${px - 3},3 L${px - 4},5 L${
    px - 6
  },6 L${px - 7},8 L${px - 9},9 L${px - 10},11 L${px - 12},12 L0,${px} Z`;

  // Per-corner anchor and transform (rotate to flip the base path).
  const anchorClass =
    corner === "top-left"
      ? "top-0 left-0"
      : corner === "bottom-left"
        ? "bottom-0 left-0"
        : "bottom-0 right-0";
  const transform =
    corner === "top-left"
      ? "rotate(0deg)"
      : corner === "bottom-left"
        ? "rotate(-90deg)"
        : "rotate(180deg)";

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute ${anchorClass}`}
      style={{ width: px, height: px, transform, transformOrigin: "center" }}
    >
      <svg
        width={px}
        height={px}
        viewBox={`0 0 ${px} ${px}`}
        className="fill-white text-white"
      >
        <path d={basePath} />
      </svg>
    </div>
  );
}

/**
 * Pen mark — three sizes, the accidental marks any rolodex card picks up
 * over years of use:
 *   - dot     a single click-bottom touch from a ballpoint
 *   - streak  a short squiggle, like the user testing pen flow
 *   - sharpie a wider, irregular smudge from accidentally brushing a
 *             marker against the card. Slightly blurred for the bleed.
 *
 * Color is supplied by the slot (or by the user when they override),
 * rendered as-is for ballpoint or with a mix-blend for sharpie so it
 * picks up the underlying card tone.
 */
function PenMark({
  shape,
  tip = "ballpoint",
  color,
  pos,
  rotate,
}: {
  shape: "dot" | "streak" | "sharpie";
  tip?: "ballpoint" | "felt";
  color: string;
  pos: Position;
  rotate: number;
}) {
  if (shape === "dot") {
    // Felt tips leave a slightly larger dot with a soft bleed halo
    // around the edge; ballpoint is a crisp, smaller circle.
    const isFelt = tip === "felt";
    return (
      <div
        aria-hidden="true"
        className="pointer-events-none absolute mix-blend-multiply"
        style={{ ...pos, transform: `rotate(${rotate}deg)` }}
      >
        {isFelt ? (
          <svg width="10" height="10" viewBox="0 0 10 10">
            <circle cx="5" cy="5" r="3.6" fill={color} opacity="0.20" />
            <circle cx="5" cy="5" r="2.8" fill={color} opacity="0.85" />
          </svg>
        ) : (
          <svg width="6" height="6" viewBox="0 0 6 6">
            <circle cx="3" cy="3" r="2.2" fill={color} opacity="0.90" />
          </svg>
        )}
      </div>
    );
  }
  if (shape === "streak") {
    const isFelt = tip === "felt";
    return (
      <div
        aria-hidden="true"
        className="pointer-events-none absolute mix-blend-multiply"
        style={{ ...pos, transform: `rotate(${rotate}deg)` }}
      >
        <svg
          width={isFelt ? 40 : 32}
          height={isFelt ? 12 : 10}
          viewBox={isFelt ? "0 0 40 12" : "0 0 32 10"}
        >
          <path
            d={
              isFelt
                ? "M2 7 Q7 2 13 6 Q19 10 25 5 Q31 1 38 7"
                : "M2 6 Q6 2 10 5 Q14 8 18 4 Q22 1 26 5 Q29 7 30 6"
            }
            stroke={color}
            strokeWidth={isFelt ? 1.8 : 1.1}
            fill="none"
            strokeLinecap="round"
            opacity={isFelt ? 0.65 : 0.75}
          />
        </svg>
      </div>
    );
  }
  // sharpie — accidental brush. Multiple overlapping blurred ellipses
  // for the irregular shape; mix-blend-multiply so it reads against
  // the card color naturally.
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute mix-blend-multiply"
      style={{ ...pos, transform: `rotate(${rotate}deg)` }}
    >
      <svg width="44" height="20" viewBox="0 0 44 20">
        <defs>
          <filter
            id="sharpie-blur"
            x="-10%"
            y="-10%"
            width="120%"
            height="120%"
          >
            <feGaussianBlur stdDeviation="1.2" />
          </filter>
        </defs>
        <g filter="url(#sharpie-blur)">
          <ellipse cx="22" cy="10" rx="20" ry="5" fill={color} opacity="0.7" />
          <ellipse cx="14" cy="9" rx="6" ry="3" fill={color} opacity="0.6" />
          <ellipse cx="32" cy="11" rx="7" ry="3" fill={color} opacity="0.6" />
          <ellipse cx="22" cy="11" rx="3" ry="2" fill={color} opacity="0.85" />
        </g>
      </svg>
    </div>
  );
}
