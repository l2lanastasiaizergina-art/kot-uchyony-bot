from pathlib import Path

STATIC_DIR = Path("src/ortho_game_bot/webapp/static")


def test_answers_are_a_two_by_two_grid_without_page_scroll() -> None:
    styles = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in styles
    assert "grid-template-rows: repeat(2, minmax(56px, 1fr))" in styles
    assert ".game-layout { height: 100svh; min-height: 0;" in styles
    assert "overflow: hidden" in styles


def test_cat_message_is_outside_the_character_stage() -> None:
    markup = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    stage_end = markup.index("</div>\n      <p id=\"cat-message\"")
    assert stage_end > markup.index('id="cat-stage"')


def test_telegram_overlay_and_wrong_answer_reaction() -> None:
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "requestFullscreen" not in script
    assert "disableVerticalSwipes" in script
    assert ': "wrong"' in script
    assert (STATIC_DIR / "assets" / "cat-wrong.webp").is_file()


def test_ai_course_has_catalog_diagnostic_and_practice_screens() -> None:
    markup = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    script = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    for element_id in (
        "open-ai-course",
        "ai-home-screen",
        "ai-diagnostic-screen",
        "ai-mission-screen",
        "ai-evidence",
    ):
        assert f'id="{element_id}"' in markup
    assert 'api("/api/ai-course")' in script
    assert 'api("/api/ai-course/missions/evidence"' in script
