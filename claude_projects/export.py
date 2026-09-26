"""Build the JSON snapshot the dashboard renders from."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .db import ProjectsDB

DASHBOARD_HTML = Path(__file__).parent / "dashboard" / "index.html"


def snapshot(db: ProjectsDB) -> dict:
    projects = []
    for p in db.list_projects():
        s = db.get_stats(project_name=p["name"])
        projects.append(
            {
                **{k: p[k] for k in ("name", "status", "themes", "url", "path", "notes", "created_at", "updated_at")},
                **s,
                "session_minutes": db.session_minutes(p["name"]),
            }
        )
    return {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "projects": projects,
        "daily": db.daily_rows(),
        "themes": db.theme_breakdown(),
        "streaks": db.streaks(),
    }


def write_site(db: ProjectsDB, out_dir: Path) -> list[Path]:
    """Write a self-contained static dashboard (index.html + data.json) to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / "index.html"
    shutil.copyfile(DASHBOARD_HTML, html)
    data = out_dir / "data.json"
    data.write_text(json.dumps(snapshot(db), indent=1))
    nojekyll = out_dir / ".nojekyll"
    nojekyll.touch()
    return [html, data, nojekyll]
