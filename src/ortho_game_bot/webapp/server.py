from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zipfile import ZipFile

from aiohttp import web

from ortho_game_bot.config import Settings
from ortho_game_bot.database import (
    ContentRepository,
    GameNotFoundError,
    InvalidOptionError,
    StaleAnswerError,
    UserRepository,
)
from ortho_game_bot.database.models import ChoiceQuestion
from ortho_game_bot.game.service import ContentUnavailableError, GameService

from .auth import InvalidInitDataError, TelegramWebUser, validate_init_data

WORD_VISUALS = {
    "жираф": "🦒",
    "жилет": "🦺",
    "снежинка": "❄️",
    "машина": "🚗",
    "шина": "🛞",
    "шишка": "🌲",
    "чашка": "☕",
    "чайник": "🫖",
    "часы": "🕰️",
    "чайка": "🐦",
    "туча": "🌧️",
    "свеча": "🕯️",
    "щавель": "🌿",
    "роща": "🌳",
    "щука": "🐟",
    "день": "☀️",
    "пень": "🪵",
    "огонь": "🔥",
    "конь": "🐴",
    "лось": "🫎",
    "гусь": "🪿",
    "дверь": "🚪",
    "тетрадь": "📓",
    "пальто": "🧥",
    "мальчик": "👦",
    "учитель": "🧑‍🏫",
    "альбом": "📒",
    "коньки": "⛸️",
    "школа": "🏫",
    "ученик": "🧑‍🎓",
    "карандаш": "✏️",
    "линейка": "📏",
    "резинка": "🧽",
    "рисунок": "🎨",
    "ребёнок": "🧒",
    "семья": "👨‍👩‍👧‍👦",
    "бабушка": "👵",
    "дедушка": "👴",
    "девочка": "👧",
    "комната": "🛋️",
    "кровать": "🛏️",
    "посуда": "🍽️",
    "молоко": "🥛",
    "обед": "🍲",
    "завтрак": "🥣",
    "ужин": "🍽️",
    "город": "🏙️",
    "улица": "🛣️",
    "дорога": "🛣️",
    "автобус": "🚌",
    "троллейбус": "🚎",
    "вагон": "🚃",
    "метро": "🚇",
    "остановка": "🚏",
    "светофор": "🚦",
    "магазин": "🏪",
    "аптека": "⚕️",
    "вокзал": "🚉",
    "берёза": "🌳",
    "ягода": "🫐",
    "капуста": "🥬",
    "морковь": "🥕",
    "огурец": "🥒",
    "помидор": "🍅",
    "яблоко": "🍎",
    "собака": "🐕",
    "корова": "🐄",
    "ворона": "🐦‍⬛",
    "воробей": "🐦",
    "сорока": "🐦",
    "заяц": "🐇",
    "вода": "💧",
    "лес": "🌲",
    "леса": "🌲",
    "гора": "⛰️",
    "моря": "🌊",
    "река": "🏞️",
    "земля": "🌍",
    "сады": "🌳",
    "трава": "🌱",
    "дуб": "🌳",
    "гриб": "🍄",
    "зуб": "🦷",
    "снег": "❄️",
    "мороз": "🥶",
    "хлеб": "🍞",
    "лодка": "🚤",
    "листья": "🍂",
    "деревья": "🌳",
    "крылья": "🪽",
    "стулья": "🪑",
    "платье": "👗",
    "варенье": "🍓",
    "печенье": "🍪",
    "вьюга": "🌨️",
    "муравьи": "🐜",
    "ручьи": "🏞️",
    "теннис": "🎾",
    "хоккей": "🏒",
    "календарь": "📅",
    "библиотека": "📚",
    "компьютер": "💻",
    "портфель": "🎒",
    "отец": "👨",
    "мать": "👩",
    "герой": "🦸",
    "минута": "⏱️",
    "секунда": "⏱️",
    "погода": "🌦️",
    "метель": "🌨️",
    "ветер": "💨",
    "облако": "☁️",
    "горизонт": "🌅",
    "ромашка": "🌼",
    "земляника": "🍓",
    "малина": "🫐",
    "лягушка": "🐸",
    "медведь": "🐻",
    "петух": "🐓",
    "курица": "🐔",
}


class MiniAppServer:
    def __init__(
        self,
        *,
        settings: Settings,
        users: UserRepository,
        content: ContentRepository,
        game_service: GameService,
    ) -> None:
        self.settings = settings
        self.users = users
        self.content = content
        self.game_service = game_service
        self.runner: web.AppRunner | None = None
        self.word_archives: dict[str, Path] = {}

    async def start(self) -> None:
        static_dir = Path(__file__).with_name("static")
        word_pack_dir = static_dir / "assets" / "word_packs"
        for archive_path in sorted(word_pack_dir.glob("*.zip")):
            with ZipFile(archive_path) as archive:
                for filename in archive.namelist():
                    self.word_archives[filename] = archive_path
        app = web.Application(client_max_size=128 * 1024)
        app["server"] = self
        app.router.add_get("/", self.index)
        app.router.add_get("/health", self.health)
        app.router.add_get("/api/bootstrap", self.bootstrap)
        app.router.add_post("/api/profile/grade", self.set_grade)
        app.router.add_post("/api/game/start", self.start_game)
        app.router.add_post("/api/game/answer", self.answer)
        app.router.add_get("/static/assets/words/{filename}", self.word_image)
        app.router.add_static("/static/", static_dir, show_index=False)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        await web.TCPSite(self.runner, "0.0.0.0", self.settings.port).start()

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def _telegram_user(self, request: web.Request) -> TelegramWebUser:
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        if not init_data and self.settings.webapp_demo:
            return TelegramWebUser(999000001, "demo", "Юный игрок")
        return validate_init_data(init_data, self.settings.bot_token)

    async def _auth(self, request: web.Request) -> TelegramWebUser:
        try:
            return await self._telegram_user(request)
        except InvalidInitDataError as exc:
            raise web.HTTPUnauthorized(text=str(exc)) from exc

    async def index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(Path(__file__).with_name("static") / "index.html")

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def word_image(self, request: web.Request) -> web.Response:
        filename = request.match_info["filename"]
        if Path(filename).name != filename or not filename.endswith(".webp"):
            raise web.HTTPNotFound()
        archive_path = self.word_archives.get(filename)
        if archive_path is None:
            raise web.HTTPNotFound()
        with ZipFile(archive_path) as archive:
            image = archive.read(filename)
        return web.Response(
            body=image,
            content_type="image/webp",
            headers={"Cache-Control": "public, max-age=2592000, immutable"},
        )

    async def bootstrap(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        user = await self.users.register_or_update(
            tg_user.id, tg_user.username, tg_user.display_name
        )
        return web.json_response({"user": self._user_json(user)})

    async def set_grade(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        payload = await request.json()
        try:
            grade = int(payload["grade"])
            user = await self.users.set_grade(tg_user.id, grade)
        except (KeyError, TypeError, ValueError, LookupError) as exc:
            raise web.HTTPBadRequest(text="Выберите класс от 1 до 11") from exc
        return web.json_response({"user": self._user_json(user)})

    async def start_game(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        user = await self.users.get(tg_user.id)
        if user is None or user.grade is None:
            raise web.HTTPConflict(text="Сначала выберите класс")
        try:
            question = await self.game_service.start_choice_round(
                user_id=tg_user.id, grade=user.grade
            )
        except ContentUnavailableError as exc:
            raise web.HTTPConflict(text=str(exc)) from exc
        return web.json_response(
            {"question": await self._question_json(question), "grade": user.grade}
        )

    async def answer(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        payload = await request.json()
        try:
            turn = await self.game_service.answer_choice(
                session_id=str(payload["session_id"]),
                user_id=tg_user.id,
                position=int(payload["position"]),
                option_index=int(payload["option"]),
            )
        except (KeyError, TypeError, ValueError, InvalidOptionError) as exc:
            raise web.HTTPBadRequest(text="Некорректный ответ") from exc
        except (GameNotFoundError, StaleAnswerError) as exc:
            raise web.HTTPConflict(text=str(exc)) from exc

        response: dict[str, Any] = {
            "outcome": asdict(turn.outcome),
            "question": (
                await self._question_json(turn.next_question)
                if turn.next_question is not None
                else None
            ),
        }
        if turn.snapshot and turn.completion:
            response["summary"] = {
                **asdict(turn.snapshot),
                **asdict(turn.completion),
            }
        return web.json_response(response)

    async def _question_json(self, question: ChoiceQuestion) -> dict[str, Any]:
        answer = await self.content.answer_by_id(question.word_id) or ""
        filename = f"{answer.casefold()}.webp"
        return {
            "session_id": question.session_id,
            "position": question.position,
            "total": question.total,
            "options": question.options,
            "group": question.group_name,
            "rule": question.rule_text,
            "visual": {
                "emoji": WORD_VISUALS.get(answer.casefold(), "🔎"),
                "image": (
                    f"/static/assets/words/{quote(filename)}"
                    if filename in self.word_archives
                    else None
                ),
            },
        }

    @staticmethod
    def _user_json(user: Any) -> dict[str, Any]:
        return {
            "id": user.telegram_id,
            "name": user.display_name,
            "grade": user.grade,
            "total_score": user.total_score,
            "monthly_score": user.monthly_score,
            "daily_streak": user.daily_streak,
        }
