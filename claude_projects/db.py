"""SQLite storage for projects, per-day git metrics, and work sessions."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB = Path.home() / ".claude-projects" / "projects.db"

STATUSES = ("active", "paused", "completed", "archived")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY,
    name       TEXT UNIQUE NOT NULL,
    path       TEXT UNIQUE NOT NULL,
    url        TEXT,
    themes     TEXT NOT NULL DEFAULT '[]',
    status     TEXT NOT NULL DEFAULT 'active',
    notes      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    day           TEXT NOT NULL,
    commits       INTEGER NOT NULL DEFAULT 0,
    lines_added   INTEGER NOT NULL DEFAULT 0,
    lines_removed INTEGER NOT NULL DEFAULT 0,
    files_changed INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (project_id, day)
);

CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    notes      TEXT
);
"""

_UPDATABLE = {"url", "themes", "status", "notes", "path"}


def resolve_db_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("CLAUDE_PROJECTS_DB")
    return Path(env).expanduser() if env else DEFAULT_DB


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


class ProjectsDB:
    def __init__(self, db_path: Path | None = None):
        self.db_path = resolve_db_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- projects -----------------------------------------------------------

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
        proj = dict(row)
        proj["themes"] = json.loads(proj["themes"])
        return proj

    def add_project(
        self,
        name: str,
        path: str | Path,
        url: str | None = None,
        themes: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO projects (name, path, url, themes, notes, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, str(path), url, json.dumps(themes or []), notes, now, now),
            )
        return self.get_project(name)  # type: ignore[return-value]

    def get_project(self, name: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()
        return self._row_to_project(row) if row else None

    def list_projects(
        self, theme: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        sql, params = "SELECT * FROM projects", []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC"
        with self._conn() as c:
            projects = [self._row_to_project(r) for r in c.execute(sql, params)]
        if theme:
            projects = [p for p in projects if theme in p["themes"]]
        return projects

    def update_project(self, name: str, **fields: Any) -> dict[str, Any]:
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"cannot update {sorted(unknown)}")
        if "status" in fields and fields["status"] not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        if "themes" in fields:
            fields["themes"] = json.dumps(fields["themes"])
        if "path" in fields:
            fields["path"] = str(fields["path"])
        fields["updated_at"] = _now()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self._conn() as c:
            cur = c.execute(
                f"UPDATE projects SET {assignments} WHERE name = ?", (*fields.values(), name)
            )
            if cur.rowcount == 0:
                raise KeyError(name)
        return self.get_project(name)  # type: ignore[return-value]

    def remove_project(self, name: str) -> None:
        with self._conn() as c:
            if c.execute("DELETE FROM projects WHERE name = ?", (name,)).rowcount == 0:
                raise KeyError(name)

    # -- metrics ------------------------------------------------------------

    def set_metrics(
        self,
        project_id: int,
        day: date | str,
        commits: int = 0,
        lines_added: int = 0,
        lines_removed: int = 0,
        files_changed: int = 0,
    ) -> None:
        """Replace the metrics for one project-day (idempotent for re-syncs)."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO metrics (project_id, day, commits, lines_added, lines_removed,"
                " files_changed) VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(project_id, day) DO UPDATE SET commits=excluded.commits,"
                " lines_added=excluded.lines_added, lines_removed=excluded.lines_removed,"
                " files_changed=excluded.files_changed",
                (project_id, str(day), commits, lines_added, lines_removed, files_changed),
            )
            c.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (_now(), project_id))

    def get_stats(
        self, project_name: str | None = None, theme: str | None = None
    ) -> dict[str, int]:
        """Aggregate metrics globally, for one project, or across a theme."""
        sql = (
            "SELECT COALESCE(SUM(m.commits),0) AS commits,"
            " COALESCE(SUM(m.lines_added),0) AS lines_added,"
            " COALESCE(SUM(m.lines_removed),0) AS lines_removed,"
            " COALESCE(SUM(m.files_changed),0) AS files_changed,"
            " COUNT(DISTINCT m.day) AS days_active,"
            " COUNT(DISTINCT m.project_id) AS projects"
            " FROM metrics m JOIN projects p ON p.id = m.project_id"
        )
        params: list[Any] = []
        if project_name:
            sql += " WHERE p.name = ?"
            params.append(project_name)
        with self._conn() as c:
            row = c.execute(sql, params).fetchone()
            stats = dict(row)
            if theme:
                ids = [p["id"] for p in self.list_projects(theme=theme)]
                if not ids:
                    return {k: 0 for k in stats}
                marks = ",".join("?" * len(ids))
                row = c.execute(
                    sql + f" WHERE m.project_id IN ({marks})", ids
                ).fetchone()
                stats = dict(row)
        return {k: int(v) for k, v in stats.items()}

    def theme_breakdown(self) -> dict[str, dict[str, int]]:
        """Per-theme totals: how much of your work lands in each interest."""
        out: dict[str, dict[str, int]] = {}
        for p in self.list_projects():
            s = self.get_stats(project_name=p["name"])
            for t in p["themes"]:
                agg = out.setdefault(t, {"projects": 0, "commits": 0, "lines_added": 0})
                agg["projects"] += 1
                agg["commits"] += s["commits"]
                agg["lines_added"] += s["lines_added"]
        return dict(sorted(out.items(), key=lambda kv: -kv[1]["commits"]))

    # -- sessions -----------------------------------------------------------

    def start_session(self, project_id: int, notes: str | None = None) -> int:
        with self._conn() as c:
            open_row = c.execute(
                "SELECT id FROM sessions WHERE ended_at IS NULL LIMIT 1"
            ).fetchone()
            if open_row:
                raise RuntimeError(f"session {open_row['id']} is still open; stop it first")
            cur = c.execute(
                "INSERT INTO sessions (project_id, started_at, notes) VALUES (?, ?, ?)",
                (project_id, _now(), notes),
            )
            return int(cur.lastrowid)

    def stop_session(self, notes: str | None = None) -> dict[str, Any]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                raise RuntimeError("no open session")
            ended = _now()
            merged = "\n".join(filter(None, [row["notes"], notes])) or None
            c.execute(
                "UPDATE sessions SET ended_at = ?, notes = ? WHERE id = ?",
                (ended, merged, row["id"]),
            )
            row = c.execute("SELECT * FROM sessions WHERE id = ?", (row["id"],)).fetchone()
        return dict(row)

    def session_minutes(self, project_name: str) -> int:
        with self._conn() as c:
            rows = c.execute(
                "SELECT s.started_at, s.ended_at FROM sessions s"
                " JOIN projects p ON p.id = s.project_id"
                " WHERE p.name = ? AND s.ended_at IS NOT NULL",
                (project_name,),
            ).fetchall()
        total = 0
        for r in rows:
            delta = datetime.fromisoformat(r["ended_at"]) - datetime.fromisoformat(r["started_at"])
            total += int(delta.total_seconds() // 60)
        return total
