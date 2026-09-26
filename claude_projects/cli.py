"""claude-projects command-line interface."""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

from . import __version__
from .db import STATUSES, ProjectsDB
from .export import write_site
from .git_sync import is_git_repo, sync_project


def _themes(arg: str | None) -> list[str]:
    return [t.strip() for t in arg.split(",") if t.strip()] if arg else []


def _table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*headers), fmt.format(*("-" * w for w in widths))]
    lines += [fmt.format(*(str(x) for x in r)) for r in rows]
    return "\n".join(lines)


def _require(db: ProjectsDB, name: str) -> dict:
    proj = db.get_project(name)
    if proj is None:
        sys.exit(f"error: no project named {name!r}")
    return proj


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="claude-projects", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--db", type=Path, help="database file (default: $CLAUDE_PROJECTS_DB or ~/.claude-projects/projects.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the database")

    a = sub.add_parser("add", help="register a project")
    a.add_argument("path")
    a.add_argument("--name", help="defaults to the folder name")
    a.add_argument("--url")
    a.add_argument("--themes", help="comma-separated, e.g. AI,ML,Architecture")
    a.add_argument("--notes")
    a.add_argument("--no-sync", action="store_true", help="skip the initial git sync")

    ls = sub.add_parser("list", help="list projects")
    ls.add_argument("--theme")
    ls.add_argument("--status", choices=STATUSES)

    s = sub.add_parser("show", help="show one project")
    s.add_argument("name")

    u = sub.add_parser("update", help="change status, themes, notes, url or path")
    u.add_argument("name")
    u.add_argument("--status", choices=STATUSES)
    u.add_argument("--themes")
    u.add_argument("--notes")
    u.add_argument("--url")
    u.add_argument("--path")

    t = sub.add_parser("tag", help="replace a project's themes")
    t.add_argument("name")
    t.add_argument("themes")

    rm = sub.add_parser("remove", help="delete a project and its metrics")
    rm.add_argument("name")

    st = sub.add_parser("stats", help="aggregate metrics")
    st.add_argument("--project")
    st.add_argument("--theme")

    sub.add_parser("themes", help="per-theme breakdown of your work")

    sy = sub.add_parser("sync", help="rebuild metrics from git history")
    sy.add_argument("name", nargs="?", help="one project (default: all)")
    sy.add_argument("--author", help="only count commits by this author")

    ss = sub.add_parser("start", help="start a work session")
    ss.add_argument("name")
    ss.add_argument("--notes")

    sp = sub.add_parser("stop", help="stop the open work session")
    sp.add_argument("--notes")

    sv = sub.add_parser("serve", help="live dashboard on localhost")
    sv.add_argument("--port", type=int, default=0, help="default: any free port")
    sv.add_argument("--no-open", action="store_true", help="don't open a browser")

    ex = sub.add_parser("export", help="write the static dashboard (index.html + data.json)")
    ex.add_argument("--out", type=Path, default=Path("docs"))

    pb = sub.add_parser("publish", help="export into a git repo's docs/, commit and push")
    pb.add_argument("--repo", type=Path, default=Path("."), help="checkout of the dashboard repo")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    db = ProjectsDB(args.db)

    if args.cmd == "init":
        print(f"database ready: {db.db_path}")

    elif args.cmd == "add":
        path = Path(args.path).expanduser().resolve()
        name = args.name or path.name
        try:
            proj = db.add_project(name, path, args.url, _themes(args.themes), args.notes)
        except sqlite3.IntegrityError:
            sys.exit(f"error: a project with that name or path already exists")
        days = 0 if args.no_sync else sync_project(db, proj)
        print(f"added {name}  themes={','.join(proj['themes']) or '-'}  synced {days} day(s)")

    elif args.cmd == "list":
        projects = db.list_projects(theme=args.theme, status=args.status)
        if not projects:
            print("no projects")
            return
        rows = []
        for p in projects:
            s = db.get_stats(project_name=p["name"])
            rows.append([p["name"], p["status"], ",".join(p["themes"]), s["commits"], p["path"]])
        print(_table(rows, ["name", "status", "themes", "commits", "path"]))

    elif args.cmd == "show":
        p = _require(db, args.name)
        s = db.get_stats(project_name=p["name"])
        for k in ("name", "status", "path", "url", "notes", "created_at", "updated_at"):
            print(f"{k:<12}{p[k] or '-'}")
        print(f"{'themes':<12}{', '.join(p['themes']) or '-'}")
        print(
            f"{'git':<12}{s['commits']} commits, +{s['lines_added']}/-{s['lines_removed']}"
            f" over {s['days_active']} day(s)"
        )
        print(f"{'sessions':<12}{db.session_minutes(p['name'])} min tracked")

    elif args.cmd == "update":
        fields = {
            k: v
            for k, v in (("status", args.status), ("notes", args.notes), ("url", args.url), ("path", args.path))
            if v is not None
        }
        if args.themes is not None:
            fields["themes"] = _themes(args.themes)
        if not fields:
            sys.exit("error: nothing to update")
        try:
            db.update_project(args.name, **fields)
        except KeyError:
            sys.exit(f"error: no project named {args.name!r}")
        print(f"updated {args.name}")

    elif args.cmd == "tag":
        _require(db, args.name)
        db.update_project(args.name, themes=_themes(args.themes))
        print(f"tagged {args.name}: {args.themes}")

    elif args.cmd == "remove":
        try:
            db.remove_project(args.name)
        except KeyError:
            sys.exit(f"error: no project named {args.name!r}")
        print(f"removed {args.name}")

    elif args.cmd == "stats":
        if args.project:
            _require(db, args.project)
        s = db.get_stats(project_name=args.project, theme=args.theme)
        for k, v in s.items():
            print(f"{k:<14}{v}")

    elif args.cmd == "themes":
        rows = [[t, a["projects"], a["commits"], a["lines_added"]] for t, a in db.theme_breakdown().items()]
        print(_table(rows, ["theme", "projects", "commits", "lines_added"]) if rows else "no themes yet")

    elif args.cmd == "sync":
        targets = [_require(db, args.name)] if args.name else db.list_projects()
        for p in targets:
            if not is_git_repo(Path(p["path"]).expanduser()):
                print(f"{p['name']:<30}not a git repo")
                continue
            print(f"{p['name']:<30}{sync_project(db, p, author=args.author)} day(s)")

    elif args.cmd == "start":
        p = _require(db, args.name)
        try:
            sid = db.start_session(p["id"], args.notes)
        except RuntimeError as e:
            sys.exit(f"error: {e}")
        print(f"session {sid} started on {p['name']}")

    elif args.cmd == "stop":
        try:
            s = db.stop_session(args.notes)
        except RuntimeError as e:
            sys.exit(f"error: {e}")
        print(f"session {s['id']} stopped ({s['started_at']} -> {s['ended_at']})")

    elif args.cmd == "serve":
        from .dashboard import serve  # imports webbrowser; keep it off the fast path

        serve(db, port=args.port, open_browser=not args.no_open)

    elif args.cmd == "export":
        files = write_site(db, args.out)
        print(f"wrote {len(files)} files to {args.out}/")

    elif args.cmd == "publish":
        repo = args.repo.expanduser().resolve()
        if not is_git_repo(repo):
            sys.exit(f"error: {repo} is not a git repo")
        write_site(db, repo / "docs")
        git = ["git", "-C", str(repo)]
        subprocess.run([*git, "add", "docs"], check=True)
        if subprocess.run([*git, "diff", "--cached", "--quiet"]).returncode == 0:
            print("dashboard unchanged; nothing to publish")
            return
        subprocess.run([*git, "commit", "-q", "-m", "dashboard: refresh snapshot"], check=True)
        subprocess.run([*git, "push"], check=True)
        print("published: pushed docs/ — the Dashboard workflow will deploy it")


if __name__ == "__main__":
    main()
