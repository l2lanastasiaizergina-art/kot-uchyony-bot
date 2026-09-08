from __future__ import annotations

import gzip
import hashlib
import json
import random
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ortho_game_bot.database.connection import Database

LANGUAGES = {"ru", "en", "kz"}
AGE_MODES = {"child", "teen", "adult"}


class ArtCultureError(RuntimeError):
    """Base error for the World Art learning module."""


class ArtCultureNotFoundError(ArtCultureError):
    pass


class ArtCultureStaleAnswerError(ArtCultureError):
    pass


class ArtCultureInvalidOptionError(ArtCultureError):
    pass


@dataclass(frozen=True, slots=True)
class ArtAnswerResult:
    session_id: str
    question_id: str
    position: int
    total: int
    is_correct: bool
    points: int
    correct_count: int
    finished: bool


class ArtCultureContent:
    """Loads the trilingual question bank and keeps answers server-side."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if self.path.suffix == ".gz":
            with gzip.open(self.path, "rt", encoding="utf-8") as content_file:
                payload = json.load(content_file)
        else:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.version = str(payload.get("version", "1"))
        self.product = self._localized(payload.get("product"), "product")
        self.mastery = payload.get("mastery")
        if not isinstance(self.mastery, dict):
            raise ValueError("Art culture pack has no mastery rules")

        raw_assets = payload.get("assets")
        raw_modules = payload.get("modules")
        raw_questions = payload.get("questions")
        if not isinstance(raw_assets, list) or not isinstance(raw_modules, list):
            raise ValueError("Art culture pack has invalid modules or assets")
        if not isinstance(raw_questions, list) or not raw_questions:
            raise ValueError("Art culture pack has no questions")

        self._assets = {str(asset["id"]): asset for asset in raw_assets}
        self._modules: dict[str, dict[str, Any]] = {}
        self._questions: dict[str, dict[str, Any]] = {}
        self._module_questions: dict[str, list[str]] = {}

        for module in raw_modules:
            module_id = str(module.get("id", ""))
            if not module_id or module_id in self._modules:
                raise ValueError(f"Invalid or repeated module id: {module_id}")
            self._localized(module.get("title"), f"module {module_id} title")
            self._localized(module.get("goal"), f"module {module_id} goal")
            self._modules[module_id] = module
            self._module_questions[module_id] = []

        for question in raw_questions:
            self._validate_question(question)
            question_id = str(question["id"])
            module_id = str(question["module_id"])
            if question_id in self._questions or module_id not in self._modules:
                raise ValueError(f"Invalid question reference: {question_id}")
            self._questions[question_id] = question
            self._module_questions[module_id].append(question_id)

        if len(self._modules) != 27 or len(self._assets) != 135 or len(self._questions) != 405:
            raise ValueError(
                "Art culture pack must contain 27 modules, 135 assets and 405 questions"
            )
        if any(len(question_ids) != 15 for question_ids in self._module_questions.values()):
            raise ValueError("Each art culture module must contain 15 questions")

    @staticmethod
    def _localized(value: Any, label: str) -> dict[str, str]:
        if not isinstance(value, dict) or any(
            not str(value.get(lang, "")).strip() for lang in LANGUAGES
        ):
            raise ValueError(f"Missing trilingual value: {label}")
        return {lang: str(value[lang]) for lang in LANGUAGES}

    def _validate_question(self, question: Any) -> None:
        if not isinstance(question, dict):
            raise ValueError("Question must be an object")
        for field in ("id", "module_id", "concept_id", "level", "format"):
            if not str(question.get(field, "")).strip():
                raise ValueError(f"Question is missing {field}")
        self._localized(question.get("prompt"), f"question {question['id']} prompt")
        self._localized(question.get("explanation"), f"question {question['id']} explanation")
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"Question {question['id']} must have four options")
        if sum(bool(option.get("is_correct")) for option in options) != 1:
            raise ValueError(f"Question {question['id']} must have one correct option")
        for option in options:
            self._localized(option.get("text"), f"option {option.get('id')} text")
            media_id = option.get("media_asset_id")
            if media_id and media_id not in self._assets:
                raise ValueError(f"Question {question['id']} references missing asset {media_id}")
        visual_id = question.get("visual_asset_id")
        if visual_id and visual_id != "FOUR_OPTION_ASSETS" and visual_id not in self._assets:
            raise ValueError(f"Question {question['id']} references missing visual {visual_id}")

    def module_ids(self) -> tuple[str, ...]:
        return tuple(self._modules)

    def module(self, module_id: str) -> dict[str, Any]:
        try:
            return self._modules[module_id]
        except KeyError as exc:
            raise ArtCultureNotFoundError("Раздел искусства не найден") from exc

    def question(self, question_id: str) -> dict[str, Any]:
        try:
            return self._questions[question_id]
        except KeyError as exc:
            raise ArtCultureNotFoundError("Вопрос не найден") from exc

    def question_ids(self, module_id: str, age_mode: str) -> tuple[str, ...]:
        self.module(module_id)
        if age_mode not in AGE_MODES:
            raise ArtCultureError("Неизвестный возрастной режим")
        question_ids = self._module_questions[module_id]
        rank_by_mode = {
            "child": {"2_VISUAL": 0, "1_FOUNDATION": 1, "3_ANALYSIS": 2},
            "teen": {"1_FOUNDATION": 0, "2_VISUAL": 1, "3_ANALYSIS": 2},
            "adult": {"1_FOUNDATION": 0, "3_ANALYSIS": 1, "2_VISUAL": 2},
        }
        ranks = rank_by_mode[age_mode]
        return tuple(
            sorted(
                question_ids,
                key=lambda item: (ranks[self.question(item)["level"]], item),
            )
        )

    def localized_module(self, module_id: str, language: str) -> dict[str, Any]:
        if language not in LANGUAGES:
            raise ArtCultureError("Неизвестный язык")
        module = self.module(module_id)
        return {
            "id": module_id,
            "title": module["title"][language],
            "goal": module["goal"][language],
            "question_count": len(self._module_questions[module_id]),
        }

    def mastery_for(self, age_mode: str) -> dict[str, int]:
        if age_mode not in AGE_MODES:
            raise ArtCultureError("Неизвестный возрастной режим")
        rule = self.mastery.get(age_mode, {})
        return {
            "overall_percent": int(rule.get("overall_percent", 80)),
            "analysis_percent": int(rule.get("analysis_percent", 70)),
        }

    def public_question(
        self,
        question_id: str,
        *,
        language: str,
        age_mode: str,
        shuffle_seed: str,
    ) -> dict[str, Any]:
        if language not in LANGUAGES or age_mode not in AGE_MODES:
            raise ArtCultureError("Некорректный режим обучения")
        question = self.question(question_id)
        options = list(question["options"])
        seed = int.from_bytes(hashlib.sha256(shuffle_seed.encode("utf-8")).digest()[:8], "big")
        random.Random(seed).shuffle(options)

        def public_option(option: dict[str, Any]) -> dict[str, Any]:
            media_id = option.get("media_asset_id")
            media = self._assets.get(media_id) if media_id else None
            return {
                "id": option["id"],
                "label": option["label"],
                "text": option["text"][language],
                "image": media["file"] if media else None,
                "alt": media["alt"][language] if media else None,
            }

        visual_id = question.get("visual_asset_id")
        visual = (
            self._assets.get(visual_id)
            if visual_id and visual_id != "FOUR_OPTION_ASSETS"
            else None
        )
        return {
            "id": question_id,
            "module_id": question["module_id"],
            "level": question["level"],
            "format": question["format"],
            "skill": question["skill"],
            "prompt": question["prompt"][language],
            "points": int(question["points"]),
            "visual": (
                {"image": visual["file"], "alt": visual["alt"][language]}
                if visual
                else None
            ),
            "options": [public_option(option) for option in options],
        }

    def answer(self, question_id: str, option_id: str, language: str) -> dict[str, Any]:
        question = self.question(question_id)
        option = next((item for item in question["options"] if item["id"] == option_id), None)
        if option is None:
            raise ArtCultureInvalidOptionError("Выберите один из четырёх вариантов")
        correct = next(item for item in question["options"] if item["is_correct"])
        return {
            "is_correct": bool(option["is_correct"]),
            "correct_option_id": correct["id"],
            "correct_answer": correct["text"][language],
            "explanation": question["explanation"][language],
            "level": question["level"],
            "points": int(question["points"]),
        }


class ArtCultureRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def start(
        self,
        *,
        user_id: int,
        module_id: str,
        age_mode: str,
        language: str,
        question_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> str:
            active = connection.execute(
                """
                SELECT id FROM art_culture_sessions
                WHERE user_id = ? AND module_id = ? AND age_mode = ? AND status = 'active'
                ORDER BY started_at DESC LIMIT 1
                """,
                (user_id, module_id, age_mode),
            ).fetchone()
            if active:
                connection.execute(
                    """
                    UPDATE art_culture_sessions
                    SET language = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (language, active["id"]),
                )
                return str(active["id"])
            session_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO art_culture_sessions(
                    id, user_id, module_id, age_mode, language, question_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, module_id, age_mode, language, json.dumps(question_ids)),
            )
            return session_id

        session_id = await self.database.write(operation)
        session = await self.get_session(user_id=user_id, session_id=session_id)
        assert session is not None
        return session

    async def get_session(self, *, user_id: int, session_id: str) -> dict[str, Any] | None:
        row = await self.database.read_one(
            "SELECT * FROM art_culture_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        if row is None:
            return None
        payload = dict(row)
        payload["question_ids"] = json.loads(payload.pop("question_ids_json"))
        return payload

    async def answer(
        self,
        *,
        user_id: int,
        session_id: str,
        question_id: str,
        option_id: str,
        level: str,
        is_correct: bool,
        points: int,
    ) -> ArtAnswerResult:
        def operation(connection: sqlite3.Connection) -> ArtAnswerResult:
            row = connection.execute(
                "SELECT * FROM art_culture_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if row is None:
                raise ArtCultureNotFoundError("Учебная сессия не найдена")
            if row["status"] != "active":
                raise ArtCultureStaleAnswerError("Эта сессия уже завершена")
            question_ids = json.loads(row["question_ids_json"])
            position = int(row["current_position"])
            if position >= len(question_ids) or question_ids[position] != question_id:
                raise ArtCultureStaleAnswerError("Вопрос уже изменился — обновите раздел")

            awarded = points if is_correct else 0
            connection.execute(
                """
                INSERT INTO art_culture_answers(
                    session_id, user_id, question_id, position, selected_option_id,
                    level, is_correct, points_awarded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    question_id,
                    position,
                    option_id,
                    level,
                    int(is_correct),
                    awarded,
                ),
            )
            next_position = position + 1
            finished = next_position == len(question_ids)
            level_column = {
                "1_FOUNDATION": "foundation",
                "2_VISUAL": "visual",
                "3_ANALYSIS": "analysis",
            }[level]
            connection.execute(
                f"""
                UPDATE art_culture_sessions
                SET current_position = ?, correct_count = correct_count + ?,
                    points = points + ?, {level_column}_correct = {level_column}_correct + ?,
                    {level_column}_total = {level_column}_total + 1,
                    status = ?, updated_at = CURRENT_TIMESTAMP,
                    completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE id = ?
                """,
                (
                    next_position,
                    int(is_correct),
                    awarded,
                    int(is_correct),
                    "completed" if finished else "active",
                    int(finished),
                    session_id,
                ),
            )
            return ArtAnswerResult(
                session_id=session_id,
                question_id=question_id,
                position=position,
                total=len(question_ids),
                is_correct=is_correct,
                points=awarded,
                correct_count=int(row["correct_count"]) + int(is_correct),
                finished=finished,
            )

        try:
            return await self.database.write(operation)
        except sqlite3.IntegrityError as exc:
            raise ArtCultureStaleAnswerError("Ответ уже сохранён") from exc

    async def progress_for_user(self, *, user_id: int, age_mode: str) -> list[dict[str, Any]]:
        rows = await self.database.read_all(
            """
            SELECT * FROM art_culture_sessions
            WHERE user_id = ? AND age_mode = ?
            ORDER BY module_id, completed_at DESC, updated_at DESC
            """,
            (user_id, age_mode),
        )
        return [dict(row) for row in rows]

    @staticmethod
    def percent(correct: int, total: int) -> int:
        return round(correct * 100 / total) if total else 0

    def summary(self, session: dict[str, Any], mastery: dict[str, int]) -> dict[str, Any]:
        total = len(json.loads(session["question_ids_json"]))
        overall = self.percent(int(session["correct_count"]), total)
        analysis = self.percent(int(session["analysis_correct"]), int(session["analysis_total"]))
        mastered = (
            session["status"] == "completed"
            and overall >= mastery["overall_percent"]
            and analysis >= mastery["analysis_percent"]
        )
        return {
            "session_id": session["id"],
            "module_id": session["module_id"],
            "age_mode": session["age_mode"],
            "status": session["status"],
            "correct_count": int(session["correct_count"]),
            "question_total": total,
            "points": int(session["points"]),
            "overall_percent": overall,
            "analysis_percent": analysis,
            "level_scores": {
                "foundation": {
                    "correct": int(session["foundation_correct"]),
                    "total": int(session["foundation_total"]),
                    "percent": self.percent(
                        int(session["foundation_correct"]),
                        int(session["foundation_total"]),
                    ),
                },
                "visual": {
                    "correct": int(session["visual_correct"]),
                    "total": int(session["visual_total"]),
                    "percent": self.percent(
                        int(session["visual_correct"]),
                        int(session["visual_total"]),
                    ),
                },
                "analysis": {
                    "correct": int(session["analysis_correct"]),
                    "total": int(session["analysis_total"]),
                    "percent": analysis,
                },
            },
            "mastered": mastered,
            "thresholds": mastery,
        }
