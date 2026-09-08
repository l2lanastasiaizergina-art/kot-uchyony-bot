from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
from dotenv import load_dotenv

from ortho_game_bot.ai_course import AICourseContent, AICourseRepository
from ortho_game_bot.art_culture import ArtCultureContent, ArtCultureRepository
from ortho_game_bot.config import Settings
from ortho_game_bot.database import (
    ContentRepository,
    Database,
    GameRepository,
    UserRepository,
)
from ortho_game_bot.game.service import GameService
from ortho_game_bot.handlers import common_router, game_router
from ortho_game_bot.leader_library import LeaderLibraryContent, LeaderLibraryRepository
from ortho_game_bot.logging_config import configure_logging
from ortho_game_bot.middlewares import RateLimitMiddleware
from ortho_game_bot.webapp import MiniAppServer

logger = logging.getLogger(__name__)


async def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    database = Database(settings.database_path)
    await database.migrate()
    content = ContentRepository(database)
    imported = await content.import_directory(settings.content_path)
    logger.info("Контент готов: добавлено %s новых слов", imported)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть главное меню"),
            BotCommand(command="profile", description="Моя статистика"),
            BotCommand(command="leaderboard", description="Топ-10 игроков"),
        ]
    )
    dispatcher = Dispatcher()
    dispatcher.message.outer_middleware(RateLimitMiddleware())
    dispatcher.callback_query.outer_middleware(RateLimitMiddleware())
    dispatcher.include_router(game_router)
    dispatcher.include_router(common_router)

    users = UserRepository(database)
    game_service = GameService(
        content,
        GameRepository(database),
        round_size=settings.round_size,
    )
    leader_library = LeaderLibraryContent(settings.leader_library_path)
    leader_library_progress = LeaderLibraryRepository(database)
    art_culture = ArtCultureContent(settings.art_culture_path)
    art_culture_progress = ArtCultureRepository(database)
    ai_course = AICourseContent(settings.ai_course_path)
    ai_course_progress = AICourseRepository(database)

    mini_app = MiniAppServer(
        settings=settings,
        users=users,
        content=content,
        game_service=game_service,
        leader_library=leader_library,
        leader_library_progress=leader_library_progress,
        art_culture=art_culture,
        art_culture_progress=art_culture_progress,
        ai_course=ai_course,
        ai_course_progress=ai_course_progress,
    )
    await mini_app.start()
    if settings.webapp_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Играть",
                web_app=WebAppInfo(url=settings.webapp_url),
            )
        )

    logger.info("Бот запущен в режиме long polling")
    try:
        await dispatcher.start_polling(
            bot,
            users=users,
            content=content,
            game_service=game_service,
            settings=settings,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await mini_app.stop()


def run() -> None:
    asyncio.run(main())
