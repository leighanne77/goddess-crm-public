"""Pull circular country-flag SVGs from the HatScripts circle-flags repo.

Source: https://github.com/HatScripts/circle-flags (MIT licensed).
The repo publishes one SVG per ISO 3166-1 alpha-2 code (lowercase) at
the gh-pages branch — e.g. `us.svg`, `sa.svg`, `gb.svg`, plus a special
`european_union.svg`. We download exactly the codes in COUNTRY_CODES
(the starter set picked in Slice 6.7), drop them into
frontend/src/assets/country-flags/, and trust the codegen script
(sync_country_codes.py) to keep the TS Literal union in sync.

Run:
    python scripts/fetch_country_flags.py            # default starter set
    python scripts/fetch_country_flags.py us sa kr   # additional codes

Idempotent: skips a file that already exists unless --force is passed.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST = REPO_ROOT / "frontend" / "src" / "assets" / "country-flags"
RAW_URL = (
    "https://raw.githubusercontent.com/HatScripts/circle-flags"
    "/gh-pages/flags/{code}.svg"
)

# Starter set picked in Phase 2 Slice 6.7 — covers DIN's likely pipeline
# across North America, Europe, Middle East, and Asia-Pacific. Grow this
# list (and re-run the script) when a new country shows up.
COUNTRY_CODES: list[str] = [
    # North America
    "us",
    "ca",
    "mx",
    # Europe (+ EU itself for non-country EU contacts)
    "gb",
    "fr",
    "de",
    "it",
    "es",
    "nl",
    "ch",
    "se",
    "european_union",
    # Middle East
    "sa",
    "ae",
    "qa",
    "kw",
    # Asia-Pacific
    "jp",
    "cn",
    "kr",
    "sg",
    "au",
    "nz",
    "in",
    "hk",
    "tw",
    # Latin America
    "br",
]


def fetch(code: str, *, force: bool = False) -> None:
    out_path = DEST / f"{code}.svg"
    if out_path.exists() and not force:
        print(f"  skip {code} (exists)")
        return
    url = RAW_URL.format(code=code)
    with urllib.request.urlopen(url, timeout=15) as resp:
        if resp.status != 200:
            raise SystemExit(f"ERROR: {url} returned HTTP {resp.status}")
        body = resp.read()
    out_path.write_bytes(body)
    print(f"  wrote {out_path.relative_to(REPO_ROOT)} ({len(body):>5} bytes)")


def main(argv: list[str]) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    force = "--force" in argv
    explicit = [c for c in argv[1:] if not c.startswith("--")]
    codes = explicit or COUNTRY_CODES
    print(f"Fetching {len(codes)} flag SVG(s) into {DEST.relative_to(REPO_ROOT)}/")
    for code in codes:
        fetch(code, force=force)


if __name__ == "__main__":
    main(sys.argv)
