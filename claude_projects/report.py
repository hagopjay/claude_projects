"""Weekly/monthly markdown activity summaries, built from the same daily rows
that back the dashboard (`db.daily_rows`)."""

from __future__ import annotations

from datetime import date, timedelta

from .db import ProjectsDB

# Trailing windows rather than calendar weeks/months: no ISO-week or
# month-length edge cases, and it matches the "last N days" framing the
# dashboard's range buttons already use.
PERIOD_DAYS = {"week": 7, "month": 30}

_METRIC_KEYS = ("commits", "lines_added", "lines_removed", "files_changed")


def build_report(
    db: ProjectsDB,
    period: str = "week",
    project: str | None = None,
    theme: str | None = None,
) -> str:
    if period not in PERIOD_DAYS:
        raise ValueError(f"period must be one of {sorted(PERIOD_DAYS)}")
    since = date.today() - timedelta(days=PERIOD_DAYS[period] - 1)
    rows = db.daily_rows(project_name=project, since=since)
    if theme:
        in_theme = {p["name"] for p in db.list_projects(theme=theme)}
        rows = [r for r in rows if r["project"] in in_theme]

    totals = {k: 0 for k in _METRIC_KEYS}
    by_project: dict[str, dict[str, int]] = {}
    active_days: set[str] = set()
    for r in rows:
        active_days.add(r["day"])
        agg = by_project.setdefault(r["project"], {k: 0 for k in _METRIC_KEYS})
        for k in _METRIC_KEYS:
            totals[k] += r[k]
            agg[k] += r[k]

    if project:
        scope = f"project `{project}`"
    elif theme:
        scope = f"theme `{theme}`"
    else:
        scope = "all projects"

    lines = [
        f"# Activity report: {period} ({since.isoformat()} to {date.today().isoformat()})",
        "",
        f"Scope: {scope}",
        "",
        f"- **{totals['commits']}** commits across **{len(by_project)}** project(s),"
        f" **{len(active_days)}** active day(s)",
        f"- **+{totals['lines_added']} / -{totals['lines_removed']}** lines,"
        f" **{totals['files_changed']}** files changed",
    ]
    # streaks() supports a project scope but not a theme scope.
    if theme is None:
        streak = db.streaks(project_name=project)
        lines.append(
            f"- current streak: **{streak['current']}** day(s)"
            f" (longest: {streak['longest']})"
        )
    lines.append("")

    if by_project:
        lines.append("| project | commits | +lines | -lines | files |")
        lines.append("|---|---:|---:|---:|---:|")
        for name, agg in sorted(by_project.items(), key=lambda kv: -kv[1]["commits"]):
            lines.append(
                f"| {name} | {agg['commits']} | {agg['lines_added']} |"
                f" {agg['lines_removed']} | {agg['files_changed']} |"
            )
    else:
        lines.append("_no activity in this period_")
    return "\n".join(lines) + "\n"
