import subprocess

import pytest

from claude_projects.cli import main
from claude_projects.db import ProjectsDB
from claude_projects.git_sync import daily_metrics, is_git_repo, sync_project


def _git(repo, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "T")
    (r / "a.txt").write_text("one\ntwo\n")
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "first", "--date", "2026-09-01T10:00:00")
    (r / "a.txt").write_text("one\n")
    (r / "b.bin").write_bytes(b"\x00\x01")
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "second", "--date", "2026-09-02T10:00:00")
    return r


def test_is_git_repo(repo, tmp_path):
    assert is_git_repo(repo)
    assert not is_git_repo(tmp_path)


def test_empty_repo_has_no_metrics(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    _git(empty, "init", "-q")
    assert is_git_repo(empty)
    assert daily_metrics(empty) == {}
    db = ProjectsDB(tmp_path / "t.db")
    assert sync_project(db, db.add_project("empty", empty)) == 0


def test_daily_metrics(repo):
    m = daily_metrics(repo)
    assert m["2026-09-01"] == {"commits": 1, "lines_added": 2, "lines_removed": 0, "files_changed": 1}
    # binary file counts as changed but contributes no line numbers
    assert m["2026-09-02"] == {"commits": 1, "lines_added": 0, "lines_removed": 1, "files_changed": 2}


def test_sync_project_and_cli(repo, tmp_path, capsys):
    db_path = tmp_path / "t.db"
    db = ProjectsDB(db_path)
    p = db.add_project("repo", repo)
    assert sync_project(db, p) == 2
    assert sync_project(db, db.add_project("plain", tmp_path / "plain")) == 0

    main(["--db", str(db_path), "sync"])
    main(["--db", str(db_path), "show", "repo"])
    out = capsys.readouterr().out
    assert "plain" in out and "not a git repo" in out
    assert "2 commits, +2/-1 over 2 day(s)" in out
