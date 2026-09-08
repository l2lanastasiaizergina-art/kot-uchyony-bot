from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zipfile import ZipFile

from aiohttp import web

from ortho_game_bot.art_culture import (
    AGE_MODES,
    LANGUAGES,
    ArtCultureContent,
    ArtCultureError,
    ArtCultureInvalidOptionError,
    ArtCultureNotFoundError,
    ArtCultureRepository,
    ArtCultureStaleAnswerError,
)
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
from ortho_game_bot.leader_library import (
    LeaderBookNotFoundError,
    LeaderLibraryContent,
    LeaderLibraryError,
    LeaderLibraryInvalidOptionError,
    LeaderLibraryRepository,
    LeaderLibraryStaleAnswerError,
    review_due,
)

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
        leader_library: LeaderLibraryContent,
        leader_library_progress: LeaderLibraryRepository,
        art_culture: ArtCultureContent,
        art_culture_progress: ArtCultureRepository,
    ) -> None:
        self.settings = settings
        self.users = users
        self.content = content
        self.game_service = game_service
        self.leader_library = leader_library
        self.leader_library_progress = leader_library_progress
        self.art_culture = art_culture
        self.art_culture_progress = art_culture_progress
        self.runner: web.AppRunner | None = None
        self.word_archives: dict[str, Path] = {}
        self.art_culture_archives: dict[str, Path] = {}

    async def start(self) -> None:
        static_dir = Path(__file__).with_name("static")
        word_pack_dir = static_dir / "assets" / "word_packs"
        art_pack_dir = static_dir / "assets" / "art_culture_packs"
        for archive_path in sorted(art_pack_dir.glob("*.zip")):
            with ZipFile(archive_path) as archive:
                for filename in archive.namelist():
                    self.art_culture_archives[filename] = archive_path
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
        app.router.add_get("/api/library/books", self.library_books)
        app.router.add_post("/api/library/books/{book_id}/start", self.library_start)
        app.router.add_get("/api/library/books/{book_id}", self.library_book)
        app.router.add_post("/api/library/answer", self.library_answer)
        app.router.add_get("/api/library/reviews", self.library_reviews)
        app.router.add_post("/api/library/reviews/answer", self.library_review_answer)
        app.router.add_get("/api/art/modules", self.art_modules)
        app.router.add_post("/api/art/modules/{module_id}/start", self.art_start)
        app.router.add_get("/api/art/sessions/{session_id}", self.art_session)
        app.router.add_post("/api/art/answer", self.art_answer)
        app.router.add_get("/api/art/diagnostic", self.art_diagnostic)
        app.router.add_get("/static/assets/art_culture/{filename}", self.art_culture_image)
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

    async def art_culture_image(self, request: web.Request) -> web.Response:
        filename = request.match_info["filename"]
        if Path(filename).name != filename or not filename.endswith(".png"):
            raise web.HTTPNotFound()
        archive_path = self.art_culture_archives.get(filename)
        if archive_path is None:
            raise web.HTTPNotFound()
        try:
            with ZipFile(archive_path) as archive:
                image = archive.read(filename)
        except KeyError as exc:
            raise web.HTTPNotFound() from exc
        return web.Response(
            body=image,
            content_type="image/png",
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

    async def library_books(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        progress_by_book = await self.leader_library_progress.all_for_user(user_id=tg_user.id)
        summaries = self.leader_library.summaries()
        books: list[dict[str, Any]] = []
        previous_completed = True
        completed_count = 0
        for summary in summaries:
            book_id = summary["book_id"]
            progress = progress_by_book.get(book_id)
            completed = bool(progress and progress["status"] == "completed")
            unlocked = previous_completed or progress is not None
            if completed:
                completed_count += 1
            books.append(
                {
                    **summary,
                    "unlocked": unlocked,
                    "status": progress["status"] if progress else "not_started",
                    "current_step": int(progress["current_step"]) if progress else 0,
                    "step_total": self.leader_library.CORE_STEP_COUNT,
                    "first_attempt_correct": (
                        int(progress["first_attempt_correct"]) if progress else 0
                    ),
                    "review_due": review_due(progress) if progress else None,
                }
            )
            previous_completed = completed
        return web.json_response(
            {
                "product": self.leader_library.product,
                "subtitle": self.leader_library.subtitle,
                "books": books,
                "completed_count": completed_count,
                "total_count": len(books),
            }
        )

    async def library_start(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        book_id = request.match_info["book_id"]
        try:
            self.leader_library.book(book_id)
            await self._ensure_library_book_unlocked(user_id=tg_user.id, book_id=book_id)
            progress = await self.leader_library_progress.ensure_started(
                user_id=tg_user.id,
                book_id=book_id,
            )
        except LeaderBookNotFoundError as exc:
            raise web.HTTPNotFound(text=str(exc)) from exc
        except LeaderLibraryError as exc:
            raise web.HTTPConflict(text=str(exc)) from exc
        return web.json_response(self._library_book_payload(book_id, progress))

    async def library_book(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        book_id = request.match_info["book_id"]
        try:
            self.leader_library.book(book_id)
        except LeaderBookNotFoundError as exc:
            raise web.HTTPNotFound(text=str(exc)) from exc
        progress = await self.leader_library_progress.get(user_id=tg_user.id, book_id=book_id)
        if progress is None:
            raise web.HTTPConflict(text="Сначала начните эту книгу")
        return web.json_response(self._library_book_payload(book_id, progress))

    async def library_answer(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        payload = await request.json()
        try:
            book_id = str(payload["book_id"])
            step_index = int(payload["step_index"])
            selected_option = int(payload["option"])
            question, _ = self.leader_library.answer_payload(
                book_id,
                step_index,
                selected_option,
            )
            result = await self.leader_library_progress.answer(
                user_id=tg_user.id,
                book_id=book_id,
                step_index=step_index,
                selected_option=selected_option,
                correct_option=int(question["correct_option"]),
                total_steps=self.leader_library.CORE_STEP_COUNT,
            )
        except (KeyError, TypeError, ValueError, LeaderLibraryInvalidOptionError) as exc:
            raise web.HTTPBadRequest(text="Некорректный ответ") from exc
        except LeaderBookNotFoundError as exc:
            raise web.HTTPNotFound(text=str(exc)) from exc
        except LeaderLibraryStaleAnswerError as exc:
            raise web.HTTPConflict(text=str(exc)) from exc

        total_score: int | None = None
        if result.points:
            score = await self.users.apply_score(
                telegram_id=tg_user.id,
                source_type="leader_library",
                source_id=book_id,
                delta=result.points,
                idempotency_key=f"leader-library:{book_id}:{step_index}",
                correct_delta=1,
            )
            total_score = score.total_score

        response: dict[str, Any] = {
            "book_id": book_id,
            "step_index": step_index,
            "attempt_number": result.attempt_number,
            "is_correct": result.is_correct,
            "allow_retry": result.allow_retry,
            "step_completed": result.step_completed,
            "mission_completed": result.mission_completed,
            "first_attempt_correct": result.first_attempt_correct,
            "points": result.points,
        }
        if total_score is not None:
            response["total_score"] = total_score
        if result.allow_retry:
            response["hint"] = question.get(
                "hint",
                "Вернись к ключевой детали эпизода и попробуй ещё раз.",
            )
            return web.json_response(response)

        response.update(
            {
                "correct_option": question["correct_option"],
                "correct_answer": question["options"][question["correct_option"]],
                "explanation": question["explanation"],
            }
        )
        if result.mission_completed:
            book = self.leader_library.book(book_id)
            response["summary"] = {
                "title": book["title"],
                "mission_title": book["mission_title"],
                "first_attempt_correct": result.first_attempt_correct,
                "step_total": self.leader_library.CORE_STEP_COUNT,
                "action_24h": book["action_24h"],
            }
        else:
            response["next_step"] = self.leader_library.public_step(
                book_id,
                step_index + 1,
            )
        return web.json_response(response)

    async def library_reviews(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        progress_by_book = await self.leader_library_progress.all_for_user(user_id=tg_user.id)
        reviews: list[dict[str, Any]] = []
        for summary in self.leader_library.summaries():
            progress = progress_by_book.get(summary["book_id"])
            due = review_due(progress) if progress else None
            if due is None:
                continue
            question = self.leader_library.review(summary["book_id"], due)
            reviews.append(
                {
                    "book_id": summary["book_id"],
                    "title": summary["title"],
                    "review_kind": due,
                    "question": self.leader_library.public_question(question),
                }
            )
        return web.json_response({"reviews": reviews})

    async def library_review_answer(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        payload = await request.json()
        try:
            book_id = str(payload["book_id"])
            review_kind = str(payload["review_kind"])
            selected_option = int(payload["option"])
            question = self.leader_library.review(book_id, review_kind)
            result = await self.leader_library_progress.record_review(
                user_id=tg_user.id,
                book_id=book_id,
                review_kind=review_kind,
                selected_option=selected_option,
                correct_option=int(question["correct_option"]),
            )
        except (KeyError, TypeError, ValueError, LeaderLibraryInvalidOptionError) as exc:
            raise web.HTTPBadRequest(text="Некорректный ответ") from exc
        except LeaderBookNotFoundError as exc:
            raise web.HTTPNotFound(text=str(exc)) from exc
        except LeaderLibraryError as exc:
            raise web.HTTPConflict(text=str(exc)) from exc
        return web.json_response(
            {
                **result,
                "correct_answer": question["options"][question["correct_option"]],
                "explanation": question["explanation"],
            }
        )

    @staticmethod
    def _art_mode(request: web.Request) -> tuple[str, str]:
        age_mode = request.query.get("age_mode", "teen")
        language = request.query.get("lang", "ru")
        if age_mode not in AGE_MODES or language not in LANGUAGES:
            raise web.HTTPBadRequest(text="Некорректный возрастной или языковой режим")
        return age_mode, language

    async def art_modules(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        age_mode, language = self._art_mode(request)
        mastery = self.art_culture.mastery_for(age_mode)
        rows = await self.art_culture_progress.progress_for_user(
            user_id=tg_user.id,
            age_mode=age_mode,
        )
        by_module: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_module.setdefault(str(row["module_id"]), []).append(row)

        modules: list[dict[str, Any]] = []
        mastered_count = 0
        for module_id in self.art_culture.module_ids():
            sessions = by_module.get(module_id, [])
            active = next((row for row in sessions if row["status"] == "active"), None)
            completed = [row for row in sessions if row["status"] == "completed"]
            best = max(
                (self.art_culture_progress.summary(row, mastery) for row in completed),
                key=lambda item: (
                    item["mastered"],
                    item["overall_percent"],
                    item["analysis_percent"],
                ),
                default=None,
            )
            if best and best["mastered"]:
                mastered_count += 1
            current = active or (completed[0] if completed else None)
            progress = None
            if current:
                question_total = len(json.loads(current["question_ids_json"]))
                progress = {
                    "status": current["status"],
                    "session_id": current["id"],
                    "current": int(current["current_position"]),
                    "total": question_total,
                    "percent": round(int(current["current_position"]) * 100 / question_total),
                }
            modules.append(
                {
                    **self.art_culture.localized_module(module_id, language),
                    "progress": progress,
                    "best": best,
                }
            )

        return web.json_response(
            {
                "product": self.art_culture.product[language],
                "age_mode": age_mode,
                "language": language,
                "mastery": mastery,
                "modules": modules,
                "mastered_count": mastered_count,
                "total_count": len(modules),
            }
        )

    async def art_start(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        module_id = request.match_info["module_id"]
        try:
            payload = await request.json()
            age_mode = str(payload.get("age_mode", "teen"))
            language = str(payload.get("lang", "ru"))
            question_ids = self.art_culture.question_ids(module_id, age_mode)
            if language not in LANGUAGES:
                raise ArtCultureError("Неизвестный язык")
            session = await self.art_culture_progress.start(
                user_id=tg_user.id,
                module_id=module_id,
                age_mode=age_mode,
                language=language,
                question_ids=question_ids,
            )
        except (ValueError, TypeError, ArtCultureError) as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        return web.json_response(self._art_session_payload(session))

    async def art_session(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        session = await self.art_culture_progress.get_session(
            user_id=tg_user.id,
            session_id=request.match_info["session_id"],
        )
        if session is None:
            raise web.HTTPNotFound(text="Учебная сессия не найдена")
        return web.json_response(self._art_session_payload(session))

    async def art_answer(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        try:
            payload = await request.json()
            session_id = str(payload["session_id"])
            question_id = str(payload["question_id"])
            option_id = str(payload["option_id"])
            session = await self.art_culture_progress.get_session(
                user_id=tg_user.id,
                session_id=session_id,
            )
            if session is None:
                raise ArtCultureNotFoundError("Учебная сессия не найдена")
            answer = self.art_culture.answer(question_id, option_id, session["language"])
            result = await self.art_culture_progress.answer(
                user_id=tg_user.id,
                session_id=session_id,
                question_id=question_id,
                option_id=option_id,
                level=answer["level"],
                is_correct=answer["is_correct"],
                points=answer["points"],
            )
        except (KeyError, TypeError, ValueError, ArtCultureInvalidOptionError) as exc:
            raise web.HTTPBadRequest(text="Некорректный ответ") from exc
        except ArtCultureNotFoundError as exc:
            raise web.HTTPNotFound(text=str(exc)) from exc
        except ArtCultureStaleAnswerError as exc:
            raise web.HTTPConflict(text=str(exc)) from exc

        total_score: int | None = None
        if result.points:
            score = await self.users.apply_score(
                telegram_id=tg_user.id,
                source_type="art_culture",
                source_id=question_id,
                delta=result.points,
                idempotency_key=f"art-culture:{tg_user.id}:{question_id}",
                correct_delta=1,
            )
            total_score = score.total_score

        response: dict[str, Any] = {
            "is_correct": result.is_correct,
            "points": result.points,
            "correct_count": result.correct_count,
            "correct_option_id": answer["correct_option_id"],
            "correct_answer": answer["correct_answer"],
            "explanation": answer["explanation"],
            "finished": result.finished,
        }
        if total_score is not None:
            response["total_score"] = total_score
        updated = await self.art_culture_progress.get_session(
            user_id=tg_user.id,
            session_id=session_id,
        )
        assert updated is not None
        if result.finished:
            response["summary"] = self.art_culture_progress.summary(
                {
                    **updated,
                    "question_ids_json": json.dumps(updated["question_ids"]),
                },
                self.art_culture.mastery_for(updated["age_mode"]),
            )
        else:
            response["next_question"] = self._art_question(updated)
            response["position"] = int(updated["current_position"])
            response["total"] = len(updated["question_ids"])
        return web.json_response(response)

    async def art_diagnostic(self, request: web.Request) -> web.Response:
        tg_user = await self._auth(request)
        age_mode, language = self._art_mode(request)
        mastery = self.art_culture.mastery_for(age_mode)
        rows = await self.art_culture_progress.progress_for_user(
            user_id=tg_user.id,
            age_mode=age_mode,
        )
        completed_by_module: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if row["status"] == "completed":
                completed_by_module.setdefault(str(row["module_id"]), []).append(row)

        module_scores: list[dict[str, Any]] = []
        for module_id in self.art_culture.module_ids():
            candidates = [
                self.art_culture_progress.summary(row, mastery)
                for row in completed_by_module.get(module_id, [])
            ]
            best = max(
                candidates,
                key=lambda item: (
                    item["mastered"],
                    item["overall_percent"],
                    item["analysis_percent"],
                ),
                default=None,
            )
            module = self.art_culture.localized_module(module_id, language)
            module_scores.append({**module, "result": best})

        completed = [item for item in module_scores if item["result"]]
        mastered = [item for item in completed if item["result"]["mastered"]]
        overall = (
            round(sum(item["result"]["overall_percent"] for item in completed) / len(completed))
            if completed
            else 0
        )
        analysis = (
            round(sum(item["result"]["analysis_percent"] for item in completed) / len(completed))
            if completed
            else 0
        )
        if not completed:
            band = "not_started"
        elif len(mastered) == len(module_scores) and analysis >= mastery["analysis_percent"]:
            band = "mastery"
        elif overall >= mastery["overall_percent"]:
            band = "confident"
        elif overall >= 60:
            band = "developing"
        else:
            band = "foundation"
        focus = sorted(
            (item for item in completed if not item["result"]["mastered"]),
            key=lambda item: (
                item["result"]["overall_percent"],
                item["result"]["analysis_percent"],
            ),
        )[:3]
        if len(focus) < 3:
            focus.extend(
                item for item in module_scores if item["result"] is None
                if item not in focus
            )
            focus = focus[:3]
        return web.json_response(
            {
                "age_mode": age_mode,
                "language": language,
                "band": band,
                "overall_percent": overall,
                "analysis_percent": analysis,
                "completed_count": len(completed),
                "mastered_count": len(mastered),
                "total_count": len(module_scores),
                "thresholds": mastery,
                "focus_modules": [
                    {"id": item["id"], "title": item["title"], "result": item["result"]}
                    for item in focus
                ],
                "modules": module_scores,
            }
        )

    def _art_question(self, session: dict[str, Any]) -> dict[str, Any] | None:
        position = int(session["current_position"])
        question_ids = session["question_ids"]
        if position >= len(question_ids):
            return None
        question_id = str(question_ids[position])
        return {
            **self.art_culture.public_question(
                question_id,
                language=session["language"],
                age_mode=session["age_mode"],
                shuffle_seed=f"{session['id']}:{question_id}",
            ),
            "position": position,
            "total": len(question_ids),
        }

    def _art_session_payload(self, session: dict[str, Any]) -> dict[str, Any]:
        module = self.art_culture.localized_module(session["module_id"], session["language"])
        payload: dict[str, Any] = {
            "session": {
                "id": session["id"],
                "module": module,
                "age_mode": session["age_mode"],
                "language": session["language"],
                "status": session["status"],
                "position": int(session["current_position"]),
                "total": len(session["question_ids"]),
                "correct_count": int(session["correct_count"]),
                "points": int(session["points"]),
            }
        }
        if session["status"] == "completed":
            payload["summary"] = self.art_culture_progress.summary(
                {
                    **session,
                    "question_ids_json": json.dumps(session["question_ids"]),
                },
                self.art_culture.mastery_for(session["age_mode"]),
            )
        else:
            payload["question"] = self._art_question(session)
        return payload

    async def _ensure_library_book_unlocked(self, *, user_id: int, book_id: str) -> None:
        book_ids = self.leader_library.book_ids()
        try:
            index = book_ids.index(book_id)
        except ValueError as exc:
            raise LeaderBookNotFoundError("Книга не найдена") from exc
        if index == 0:
            return
        current = await self.leader_library_progress.get(user_id=user_id, book_id=book_id)
        if current is not None:
            return
        previous = await self.leader_library_progress.get(
            user_id=user_id,
            book_id=book_ids[index - 1],
        )
        if previous is None or previous["status"] != "completed":
            raise LeaderLibraryError("Сначала завершите предыдущую книгу")

    def _library_book_payload(
        self,
        book_id: str,
        progress: dict[str, Any],
    ) -> dict[str, Any]:
        book = self.leader_library.book(book_id)
        payload: dict[str, Any] = {
            "book": {
                "book_id": book["book_id"],
                "title": book["title"],
                "author": book["author"],
                "mission_title": book["mission_title"],
                "hook": book["hook"],
            },
            "progress": {
                "status": progress["status"],
                "current_step": int(progress["current_step"]),
                "step_total": self.leader_library.CORE_STEP_COUNT,
                "first_attempt_correct": int(progress["first_attempt_correct"]),
                "answers_count": int(progress["answers_count"]),
            },
        }
        if progress["status"] == "completed":
            payload["summary"] = {
                "first_attempt_correct": int(progress["first_attempt_correct"]),
                "step_total": self.leader_library.CORE_STEP_COUNT,
                "action_24h": book["action_24h"],
                "review_due": review_due(progress),
            }
        else:
            payload["step"] = self.leader_library.public_step(
                book_id,
                int(progress["current_step"]),
            )
        return payload

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
