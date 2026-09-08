from __future__ import annotations

import pytest

from ortho_game_bot.config import Settings


def test_bot_token_is_required_for_normal_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("WEBAPP_DEMO", raising=False)
    monkeypatch.delenv("BOT_POLLING_ENABLED", raising=False)

    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        Settings.from_env()


def test_web_only_demo_can_start_without_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("WEBAPP_DEMO", "true")
    monkeypatch.setenv("BOT_POLLING_ENABLED", "false")

    settings = Settings.from_env()

    assert settings.bot_token == ""
    assert settings.webapp_demo is True
    assert settings.bot_polling_enabled is False


def test_non_demo_webapp_still_needs_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("WEBAPP_DEMO", "false")
    monkeypatch.setenv("BOT_POLLING_ENABLED", "false")

    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        Settings.from_env()
