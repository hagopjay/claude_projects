from datetime import date

from claude_projects.cli import main
from claude_projects.db import ProjectsDB


def test_add_guesses_themes_from_readme(tmp_path, capsys):
    db_path = tmp_path / "t.db"
    seed = tmp_path / "seed"
    seed.mkdir()
    main(["--db", str(db_path), "add", str(seed), "--themes", "AI"])
    capsys.readouterr()

    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    (proj_dir / "README.md").write_text("An AI experiment.")
    main(["--db", str(db_path), "add", str(proj_dir), "--no-sync"])
    out = capsys.readouterr().out
    assert "guessed themes from README/CLAUDE.md: AI" in out
    assert ProjectsDB(db_path).get_project("proj")["themes"] == ["AI"]


def test_add_explicit_themes_skip_guessing(tmp_path, capsys):
    db_path = tmp_path / "t.db"
    seed = tmp_path / "seed"
    seed.mkdir()
    main(["--db", str(db_path), "add", str(seed), "--themes", "AI"])
    capsys.readouterr()

    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    (proj_dir / "README.md").write_text("An AI experiment.")
    main(["--db", str(db_path), "add", str(proj_dir), "--themes", "Other", "--no-sync"])
    out = capsys.readouterr().out
    assert "guessed themes" not in out
    assert ProjectsDB(db_path).get_project("proj")["themes"] == ["Other"]


def test_show_and_stats_print_streak(tmp_path, capsys):
    db_path = tmp_path / "t.db"
    db = ProjectsDB(db_path)
    p = db.add_project("a", tmp_path / "a")
    db.set_metrics(p["id"], date.today(), commits=1)

    main(["--db", str(db_path), "show", "a"])
    assert "1 day(s) (longest 1)" in capsys.readouterr().out

    main(["--db", str(db_path), "stats", "--project", "a"])
    out = capsys.readouterr().out
    assert f"{'streak_now':<14}1" in out
    assert f"{'streak_best':<14}1" in out


def test_report_cli_stdout_and_file(tmp_path, capsys):
    db_path = tmp_path / "t.db"
    db = ProjectsDB(db_path)
    p = db.add_project("a", tmp_path / "a")
    db.set_metrics(p["id"], date.today(), commits=2)

    main(["--db", str(db_path), "report"])
    assert "# Activity report: week" in capsys.readouterr().out

    out_file = tmp_path / "report.md"
    main(["--db", str(db_path), "report", "--period", "month", "--out", str(out_file)])
    assert "wrote" in capsys.readouterr().out
    assert "# Activity report: month" in out_file.read_text()
