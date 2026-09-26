import json
import threading
import urllib.request

from claude_projects.cli import main
from claude_projects.dashboard import make_server
from claude_projects.db import ProjectsDB
from claude_projects.export import snapshot, write_site


def _seed(tmp_path):
    db = ProjectsDB(tmp_path / "t.db")
    p = db.add_project("a", tmp_path / "a", themes=["AI"], url="https://x")
    db.set_metrics(p["id"], "2026-09-01", commits=3, lines_added=10)
    db.set_metrics(p["id"], "2026-09-03", commits=1)
    db.add_project("b", tmp_path / "b", themes=["Maths"])
    return db


def test_snapshot_shape(tmp_path):
    snap = snapshot(_seed(tmp_path))
    assert {p["name"] for p in snap["projects"]} == {"a", "b"}
    a = next(p for p in snap["projects"] if p["name"] == "a")
    assert a["commits"] == 4 and a["days_active"] == 2 and a["themes"] == ["AI"]
    assert [d["day"] for d in snap["daily"]] == ["2026-09-01", "2026-09-03"]
    assert snap["themes"]["AI"]["commits"] == 4
    json.dumps(snap)  # must be serialisable as-is


def test_write_site(tmp_path):
    out = tmp_path / "site"
    files = write_site(_seed(tmp_path), out)
    assert {f.name for f in files} == {"index.html", "data.json", ".nojekyll"}
    html = (out / "index.html").read_text()
    assert "<title>Projects Dashboard</title>" in html
    assert 'fetch("data.json' in html  # charts are built client-side from the sidecar
    assert json.loads((out / "data.json").read_text())["projects"]


def test_server_serves_live_data(tmp_path):
    db = _seed(tmp_path)
    httpd = make_server(db, port=0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        html = urllib.request.urlopen(base + "/").read().decode()
        assert "<title>Projects Dashboard</title>" in html
        before = json.loads(urllib.request.urlopen(base + "/data.json").read())
        db.add_project("c", tmp_path / "c")
        after = json.loads(urllib.request.urlopen(base + "/data.json?x=1").read())
        assert len(after["projects"]) == len(before["projects"]) + 1
        try:
            urllib.request.urlopen(base + "/nope")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_cli_export(tmp_path, capsys):
    db_path = _seed(tmp_path).db_path
    main(["--db", str(db_path), "export", "--out", str(tmp_path / "docs")])
    assert (tmp_path / "docs" / "data.json").exists()
    assert "docs" in capsys.readouterr().out
