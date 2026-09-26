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
- `claude_projects/export.py` — `snapshot(db)` is the one JSON contract between the DB and the dashboard (`projects[]` with stats merged in, `daily[]` project-day rows, `themes{}`); `write_site` copies the HTML and writes `data.json` + `.nojekyll`.
- `claude_projects/dashboard.py` — stdlib `ThreadingHTTPServer`; `/` serves the packaged HTML, `/data.json` calls `snapshot` per request (no caching, `Cache-Control: no-store`). Port 0 = OS-assigned free port.
- `claude_projects/dashboard/index.html` — single self-contained page, no CDN. Fetches `data.json` next to it, so the identical file works under `serve` and on GitHub Pages. All aggregation (range filter, weekly buckets, per-theme totals) happens client-side, so `snapshot` stays raw. Charts are inline SVG built from template strings; single series, slot-1 blue from the dataviz reference palette, light/dark tokens on `:root` under both the media query and `[data-theme]` scopes. It is shipped as package data (`pyproject.toml`), so a new asset must be listed there too.
- `.github/workflows/dashboard.yml` — deploys `docs/` (written by `publish`) to Pages and as an artifact; triggered only by `docs/**` pushes. `ci.yml` ignores `docs/**` so snapshot refreshes don't burn test runs.

## Conventions

- No third-party runtime dependencies; keep it that way (the point is `pipx install` and forget).
- Themes are a free-form JSON list on the project row; filtering happens in Python after the query, not with `LIKE` on the JSON string.
- Dates in `metrics.day` are `YYYY-MM-DD` strings (from git `%as`); timestamps elsewhere are ISO-8601 without microseconds.
- Roadmap items (dashboard `serve`, `report`) should read the DB through `ProjectsDB`, not open sqlite directly.
