from __future__ import annotations

import argparse
import asyncio

from dotenv import load_dotenv

from ortho_game_bot.config import Settings
from ortho_game_bot.database import ContentRepository, Database


async def _initialize(*, import_words: bool) -> None:
    load_dotenv()
    settings = Settings.from_env(require_token=False)
    database = Database(settings.database_path)
    await database.migrate()
    print(f"База данных готова: {settings.database_path}")
    if import_words:
        amount = await ContentRepository(database).import_directory(settings.content_path)
        counts = await ContentRepository(database).counts_by_grade()
        print(f"Добавлено новых слов: {amount}; активный контент: {counts}")


def init_db() -> None:
    asyncio.run(_initialize(import_words=False))


def import_content() -> None:
    parser = argparse.ArgumentParser(description="Импорт словарных пакетов в SQLite")
    parser.parse_args()
    asyncio.run(_initialize(import_words=True))

