# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`claude-projects`: a stdlib-only Python CLI + SQLite store that tracks personal projects, the themes they belong to, per-day git metrics, and manual work sessions. Single user, local only. See README.md for the command surface.

## Commands

```bash
python -m pytest -q                  # full suite (tmp_path DBs + throwaway git repos; no network)
python -m pytest tests/test_git_sync.py -q
python -m claude_projects --db /tmp/x.db list    # run from a checkout without installing
CLAUDE_PROJECTS_DB=/tmp/x.db python -m claude_projects sync
```

Never run the CLI against the default DB (`~/.claude-projects/projects.db`) in tests or smoke checks — pass `--db` or set `CLAUDE_PROJECTS_DB`.

## Structure

- `claude_projects/db.py` — `ProjectsDB`. All SQL lives here. Connections are per-call via the `_conn()` context manager (commit on success, always close, `foreign_keys=ON` so `remove_project` cascades). `update_project` whitelists columns (`_UPDATABLE`) because it builds the SET clause from kwargs. `get_stats` always returns the same six int keys regardless of scope — the CLI relies on that.
- `claude_projects/git_sync.py` — `daily_metrics(path)` parses `git log --format=\x1e%as --numstat --no-merges`. The `\x1e` marker is split on `"\n"`, not `splitlines()`, which would treat `\x1e` as a line break. `sync_project` calls `set_metrics` (upsert by `(project_id, day)`), so a re-sync replaces rather than accumulates.
- `claude_projects/cli.py` — argparse; `main(argv)` takes an argv list so tests can drive it. User-facing errors go through `sys.exit("error: …")`.

## Conventions

- No third-party runtime dependencies; keep it that way (the point is `pipx install` and forget).
- Themes are a free-form JSON list on the project row; filtering happens in Python after the query, not with `LIKE` on the JSON string.
- Dates in `metrics.day` are `YYYY-MM-DD` strings (from git `%as`); timestamps elsewhere are ISO-8601 without microseconds.
- Roadmap items (dashboard `serve`, `report`) should read the DB through `ProjectsDB`, not open sqlite directly.
