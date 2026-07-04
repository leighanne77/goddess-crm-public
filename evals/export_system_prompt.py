"""Write the production system prompt to system_prompt.txt for the eval harness.

Keeps the eval in sync with app/routers/chat.py — no hand-copied drift. The
generated file is gitignored; run this before `promptfoo eval`.

Run (from the repo root, with the venv active):
    python evals/export_system_prompt.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.routers.chat import _system_prompt  # noqa: E402

out = pathlib.Path(__file__).resolve().parent / "system_prompt.txt"
out.write_text(_system_prompt("text"))
print(f"wrote {out.relative_to(out.parent.parent)} ({len(out.read_text())} chars)")
