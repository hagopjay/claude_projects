from claude_projects.theme_suggest import suggest_themes


def test_no_known_themes_suggests_nothing(tmp_path):
    (tmp_path / "README.md").write_text("An AI project about ML.")
    assert suggest_themes(tmp_path, known_themes=set()) == []


def test_matches_are_word_bounded_and_case_insensitive(tmp_path):
    (tmp_path / "README.md").write_text("A machine-learning tool, said to help with ai.")
    # "AI" should match "ai" but a naive substring match would also wrongly hit "said"
    assert suggest_themes(tmp_path, known_themes={"AI", "Maths"}) == ["AI"]


def test_orders_by_first_appearance_and_respects_limit(tmp_path):
    (tmp_path / "README.md").write_text("Covers Maths first, then AI, then Architecture.")
    assert suggest_themes(tmp_path, known_themes={"AI", "Maths", "Architecture"}) == [
        "Maths",
        "AI",
        "Architecture",
    ]
    assert suggest_themes(tmp_path, known_themes={"AI", "Maths", "Architecture"}, limit=1) == ["Maths"]


def test_reads_claude_and_agents_md_too(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Unity/Unreal 3D project.")
    assert suggest_themes(tmp_path, known_themes={"3D"}) == ["3D"]
    (tmp_path / "AGENTS.md").write_text("Sports modelling with Python.")
    assert suggest_themes(tmp_path, known_themes={"Sports"}) == ["Sports"]


def test_no_matching_files_suggests_nothing(tmp_path):
    assert suggest_themes(tmp_path, known_themes={"AI"}) == []
