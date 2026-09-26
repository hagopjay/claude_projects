"""Guess themes for a new project from words already in use elsewhere.

Purely local and deterministic — no LLM call, nothing leaves the machine,
matching the rest of this tool. It only ever narrows to themes you've already
tagged some other project with, so a fresh database with no themes yet simply
suggests nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

_CANDIDATE_FILES = ("README.md", "CLAUDE.md", "AGENTS.md")


def suggest_themes(path: Path, known_themes: set[str], limit: int = 5) -> list[str]:
    """Match known theme names against words in the project's README/CLAUDE.md/AGENTS.md.

    Case-insensitive, word-boundary matching (so "AI" matches "AI-powered" but
    not "said"). Results are ordered by first appearance in the concatenated
    text, capped at `limit`.
    """
    if not known_themes:
        return []
    text = ""
    for name in _CANDIDATE_FILES:
        f = path / name
        if f.is_file():
            try:
                text += "\n" + f.read_text(errors="ignore")
            except OSError:
                continue
    if not text:
        return []
    hits: list[tuple[int, str]] = []
    for theme in known_themes:
        m = re.search(rf"\b{re.escape(theme)}\b", text, re.IGNORECASE)
        if m:
            hits.append((m.start(), theme))
    hits.sort()
    return [theme for _, theme in hits[:limit]]
