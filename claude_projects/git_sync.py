"""Derive per-day metrics for a project from its git history."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path

from .db import ProjectsDB

_SEP = "\x1e"


def _git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    ).stdout


def is_git_repo(path: Path) -> bool:
    try:
        return _git(path, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def daily_metrics(path: Path, author: str | None = None) -> dict[str, dict[str, int]]:
    """Return {YYYY-MM-DD: {commits, lines_added, lines_removed, files_changed}}."""
    args = ["log", f"--format={_SEP}%as", "--numstat", "--no-merges"]
    if author:
        args.append(f"--author={author}")
    try:
        out = _git(path, *args)
    except subprocess.CalledProcessError as e:
        if "does not have any commits" in e.stderr:
            return {}
        raise

    days: dict[str, dict[str, int]] = defaultdict(
        lambda: {"commits": 0, "lines_added": 0, "lines_removed": 0, "files_changed": 0}
    )
    current = None
    # str.splitlines() treats \x1e as a line break, which would split the marker.
    for line in out.split("\n"):
        if line.startswith(_SEP):
            current = line[1:].strip()
            days[current]["commits"] += 1
            continue
        if not current or not line.strip():
            continue
        added, removed, _ = line.split("\t", 2)
        d = days[current]
        d["files_changed"] += 1
        if added != "-":  # binary files report "-"
            d["lines_added"] += int(added)
            d["lines_removed"] += int(removed)
    return dict(days)


def sync_project(db: ProjectsDB, project: dict, author: str | None = None) -> int:
    """Rewrite the project's metrics from git; returns number of days recorded."""
    path = Path(project["path"]).expanduser()
    if not is_git_repo(path):
        return 0
    days = daily_metrics(path, author=author)
    for day, m in days.items():
        db.set_metrics(project["id"], day, **m)
    return len(days)
