"""Локальный просмотр Mini App без подключения к Telegram."""

from __future__ import annotations

import asyncio
from pathlib import Path

from ortho_game_bot.config import Settings
from ortho_game_bot.database import ContentRepository, Database, GameRepository, UserRepository
from ortho_game_bot.game.service import GameService
from ortho_game_bot.webapp import MiniAppServer


async def main() -> None:
    database = Database(Path("var/preview.sqlite3"))
    await database.migrate()
    content = ContentRepository(database)
    await content.import_directory(Path("data/words"))
    users = UserRepository(database)
    service = GameService(content, GameRepository(database), round_size=10)
    settings = Settings(
        bot_token="preview-token",
        admin_ids=frozenset(),
        database_path=Path("var/preview.sqlite3"),
        content_path=Path("data/words"),
        webapp_demo=True,
        port=8080,
    )
    server = MiniAppServer(
        settings=settings,
        users=users,
        content=content,
        game_service=service,
    )
    await server.start()
    print("Mini App preview: http://127.0.0.1:8080")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
