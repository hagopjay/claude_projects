import sqlite3

import pytest

from claude_projects.db import ProjectsDB


@pytest.fixture
def db(tmp_path):
    return ProjectsDB(tmp_path / "t.db")


def test_add_and_get(db, tmp_path):
    p = db.add_project("alpha", tmp_path, url="u", themes=["AI", "ML"], notes="n")
    assert p["themes"] == ["AI", "ML"]
    assert p["status"] == "active"
    assert db.get_project("alpha")["url"] == "u"
    assert db.get_project("missing") is None


def test_duplicate_name_rejected(db, tmp_path):
    db.add_project("alpha", tmp_path / "a")
    with pytest.raises(sqlite3.IntegrityError):
        db.add_project("alpha", tmp_path / "b")


def test_theme_filter_keeps_every_match(db, tmp_path):
    # the prototype removed items while iterating and silently skipped matches
    for i in range(5):
        db.add_project(f"p{i}", tmp_path / str(i), themes=["AI"])
    db.add_project("other", tmp_path / "o", themes=["Maths"])
    assert {p["name"] for p in db.list_projects(theme="AI")} == {f"p{i}" for i in range(5)}
    assert db.list_projects(theme="Nope") == []


def test_update_whitelist_and_status(db, tmp_path):
    db.add_project("alpha", tmp_path)
    assert db.update_project("alpha", status="completed", themes=["X"])["themes"] == ["X"]
    with pytest.raises(ValueError):
        db.update_project("alpha", status="done")
    with pytest.raises(ValueError):
        db.update_project("alpha", id=99)
    with pytest.raises(KeyError):
        db.update_project("ghost", notes="x")


def test_metrics_upsert_is_idempotent(db, tmp_path):
    p = db.add_project("alpha", tmp_path)
    db.set_metrics(p["id"], "2026-09-01", commits=2, lines_added=10)
    db.set_metrics(p["id"], "2026-09-01", commits=3, lines_added=15)
    db.set_metrics(p["id"], "2026-09-02", commits=1, lines_added=1)
    s = db.get_stats(project_name="alpha")
    assert (s["commits"], s["lines_added"], s["days_active"]) == (4, 16, 2)


def test_stats_scopes(db, tmp_path):
    a = db.add_project("a", tmp_path / "a", themes=["AI"])
    b = db.add_project("b", tmp_path / "b", themes=["Maths"])
    db.set_metrics(a["id"], "2026-09-01", commits=5)
    db.set_metrics(b["id"], "2026-09-01", commits=2)
    assert db.get_stats()["commits"] == 7
    assert db.get_stats(theme="AI")["commits"] == 5
    assert db.get_stats(theme="Nope")["commits"] == 0
    assert db.get_stats(project_name="nobody")["commits"] == 0
    assert db.theme_breakdown()["AI"] == {"projects": 1, "commits": 5, "lines_added": 0}


def test_remove_cascades(db, tmp_path):
    p = db.add_project("a", tmp_path)
    db.set_metrics(p["id"], "2026-09-01", commits=1)
    db.remove_project("a")
    assert db.get_stats()["commits"] == 0
    with pytest.raises(KeyError):
        db.remove_project("a")


def test_sessions(db, tmp_path):
    p = db.add_project("a", tmp_path)
    sid = db.start_session(p["id"], "first")
    with pytest.raises(RuntimeError):
        db.start_session(p["id"])
    s = db.stop_session("done")
    assert s["id"] == sid and s["notes"] == "first\ndone"
    assert db.session_minutes("a") >= 0
    with pytest.raises(RuntimeError):
        db.stop_session()
