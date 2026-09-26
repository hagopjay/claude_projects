# claude-projects

A small, local, git-aware tracker for the projects you work on and the themes
they belong to (AI, ML theory, architecture interview prep, futures/sports
modelling, 3D/Unity/Unreal/three.js, …). One SQLite file, zero dependencies,
nothing leaves your machine.

```
$ claude-projects list
name             status  themes                      commits  path
---------------  ------  --------------------------  -------  ----------------------------
graphify         active  AI,Documentation,Learning   1436     /home/you/src/graphify
claude_projects  active  Tools,Python,Architecture   3        /home/you/src/claude_projects
math-ml-study    active  ML,Maths,Theory             0        /home/you/study/math-ml

$ claude-projects themes
theme          projects  commits  lines_added
-------------  --------  -------  -----------
AI             1         1436     412903
Documentation  1         1436     412903
...
```

## Install

```bash
pipx install git+https://github.com/hagopjay/claude_projects   # or: pip install .
claude-projects init
```

Works without installing too: `python -m claude_projects …` from a checkout.

## Use

```bash
claude-projects add ~/src/thing --themes AI,ML --url https://github.com/you/thing
claude-projects list [--theme AI] [--status active|paused|completed|archived]
claude-projects show thing
claude-projects update thing --status completed --notes "shipped v1"
claude-projects tag thing AI,ML,Visualization
claude-projects remove thing

claude-projects sync [thing] [--author you@example.com]   # rebuild metrics from git log
claude-projects stats [--project thing | --theme AI]
claude-projects themes                                    # where your effort actually goes

claude-projects start thing --notes "reading Leiden paper"
claude-projects stop --notes "done"
```

`add` syncs from git immediately. `sync` is idempotent — it rewrites each
project-day from `git log --numstat`, so re-running never double-counts.

## Dashboard

```bash
claude-projects serve            # live, on a free localhost port; opens your browser
claude-projects serve --port 8765 --no-open
```

`serve` rebuilds `data.json` from the DB on every request, so it is always
current — leave it running in a tab. Hero commit count with a vs-previous-period
delta, stat tiles, commits per week, commits by theme, and a project table, with
a 30d / 90d / 1y / all range switch. Light and dark follow your OS.

### Publish it through GitHub Actions

The same page works as a static site: `index.html` + a `data.json` snapshot.

```bash
cd ~/src/claude_projects          # a checkout of this repo (or any repo with the workflow)
claude-projects publish           # export -> docs/, commit "dashboard: refresh snapshot", push
```

`.github/workflows/dashboard.yml` runs on every push that touches `docs/` and:

1. attaches `docs/` as a downloadable **artifact** (works on every plan, private repos included), and
2. deploys it to **GitHub Pages** when Pages is enabled for the repo
   (Settings → Pages → Source: *GitHub Actions*). Pages on a **private** repo
   needs GitHub Pro/Team; on Free, either make the repo public or use the artifact.

Only the snapshot is published — never the database. Want it refreshed
automatically? Put `claude-projects publish --repo ~/src/claude_projects` in the
post-commit hook below, or on a cron.

To just write the files without git: `claude-projects export --out some/dir`.

### Keep it current automatically

Add to any tracked repo's `.git/hooks/post-commit` (make it executable):

```bash
#!/bin/sh
claude-projects sync "$(basename "$(git rev-parse --show-toplevel)")" >/dev/null 2>&1 &
```

### Where the data lives

`~/.claude-projects/projects.db`, or wherever `CLAUDE_PROJECTS_DB` / `--db` points.
Back it up like any file; `sqlite3 ~/.claude-projects/projects.db .dump` is enough.

## Schema

| table | key | what |
|---|---|---|
| `projects` | `name` (unique), `path` (unique) | url, `themes` (JSON list), status, notes, timestamps |
| `metrics` | `(project_id, day)` | commits, lines_added, lines_removed, files_changed — derived from git |
| `sessions` | `id` | started_at, ended_at, notes — manual time tracking |

## Roadmap

- streaks and per-project timelines on the dashboard
- `report`: weekly/monthly markdown summary
- theme suggestions from README / CLAUDE.md keywords on `add`
- non-git activity (notes, papers read) as first-class entries

## Development

```bash
pip install -e '.[dev]'   # or: uv sync
python -m pytest -q
```
