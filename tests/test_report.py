from datetime import date, timedelta

import pytest

from claude_projects.db import ProjectsDB
from claude_projects.report import build_report


@pytest.fixture
def db(tmp_path):
    return ProjectsDB(tmp_path / "t.db")


def test_rejects_unknown_period(db):
    with pytest.raises(ValueError):
        build_report(db, period="year")


def test_empty_report_says_no_activity(db):
    text = build_report(db, period="week")
    assert "Scope: all projects" in text
    assert "_no activity in this period_" in text
    assert "**0** commits" in text


def test_report_totals_and_table(db, tmp_path):
    a = db.add_project("a", tmp_path / "a", themes=["AI"])
    b = db.add_project("b", tmp_path / "b", themes=["Maths"])
    today = date.today()
    db.set_metrics(a["id"], today, commits=3, lines_added=10, lines_removed=2)
    db.set_metrics(b["id"], today - timedelta(days=1), commits=1, lines_added=1)
    # outside the trailing-week window entirely
    db.set_metrics(b["id"], today - timedelta(days=20), commits=99)

    text = build_report(db, period="week")
    assert "**4** commits across **2** project(s)" in text
    assert "| a | 3 | 10 | 2 | " in text
    assert "99" not in text  # old activity excluded from the window


def test_report_scoped_to_project(db, tmp_path):
    a = db.add_project("a", tmp_path / "a")
    db.add_project("b", tmp_path / "b")
    db.set_metrics(a["id"], date.today(), commits=5)
    text = build_report(db, period="week", project="a")
    assert "Scope: project `a`" in text
    assert "**5** commits across **1** project(s)" in text


def test_report_scoped_to_theme_skips_streak_line(db, tmp_path):
    a = db.add_project("a", tmp_path / "a", themes=["AI"])
    db.set_metrics(a["id"], date.today(), commits=2)
    text = build_report(db, period="week", theme="AI")
    assert "Scope: theme `AI`" in text
    assert "streak" not in text
