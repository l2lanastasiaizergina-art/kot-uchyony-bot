from __future__ import annotations

import gzip
import json
import random
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ortho_game_bot.database.connection import Database

TEST_MODES = {
    "en_to_ru": "Английский → русский",
    "spelling": "Правильное написание",
    "ru_to_en": "Русский → английский",
}
REVIEW_INTERVALS = (1, 3, 7, 14)


class EnglishVocabularyError(RuntimeError):
    """Base error for the Wise Cat English vocabulary module."""


class EnglishVocabularyNotFoundError(EnglishVocabularyError):
    pass


class EnglishVocabularyStaleAnswerError(EnglishVocabularyError):
    pass


class EnglishVocabularyInvalidOptionError(EnglishVocabularyError):
    pass


@dataclass(frozen=True, slots=True)
class EnglishAnswerResult:
    session_id: str
    question_id: str
    position: int
    total: int
    is_correct: bool
    points: int
    correct_count: int
    current_streak: int
    best_streak: int
    finished: bool


class EnglishVocabularyContent:
    """Loads the levelled vocabulary bank and keeps answer keys server-side."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if self.path.suffix == ".gz":
            with gzip.open(self.path, "rt", encoding="utf-8") as source:
                payload = json.load(source)
        else:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata")
        raw_levels = payload.get("levels")
        raw_vocabulary = payload.get("vocabulary")
        raw_tests = payload.get("tests")
        if not isinstance(metadata, dict):
            raise ValueError("English vocabulary pack has no metadata")
        if not isinstance(raw_levels, list) or len(raw_levels) != 6:
            raise ValueError("English vocabulary pack must contain six levels")
        if not isinstance(raw_vocabulary, list) or len(raw_vocabulary) != 480:
            raise ValueError("English vocabulary pack must contain 480 words")
        if not isinstance(raw_tests, dict):
            raise ValueError("English vocabulary pack has no tests")

        self.metadata = metadata
        self._levels: dict[str, dict[str, Any]] = {}
        self._questions: dict[str, dict[str, Any]] = {}
        self._question_ids: dict[tuple[str, str], list[str]] = {}

        for level in raw_levels:
            code = str(level.get("code", ""))
            if not code or code in self._levels:
                raise ValueError(f"Invalid or repeated English level: {code}")
            if not str(level.get("name", "")).strip() or not str(level.get("cefr", "")).strip():
                raise ValueError(f"English level {code} has no name or CEFR value")
            self._levels[code] = level

        for mode in TEST_MODES:
            bank = raw_tests.get(mode)
            if not isinstance(bank, list) or len(bank) != 480:
                raise ValueError(f"English test bank {mode} must contain 480 questions")
            for question in bank:
                self._validate_question(question, mode)
                question_id = str(question["question_id"])
                level_code = str(question["level_code"])
                if question_id in self._questions or level_code not in self._levels:
                    raise ValueError(f"Invalid English question reference: {question_id}")
                self._questions[question_id] = question
                self._question_ids.setdefault((level_code, mode), []).append(question_id)

        if any(len(ids) != 80 for ids in self._question_ids.values()):
            raise ValueError("Each English level and mode must contain 80 questions")

    @staticmethod
    def _validate_question(question: Any, mode: str) -> None:
        if not isinstance(question, dict):
            raise ValueError("English question must be an object")
        for field in ("question_id", "word_id", "level_code", "prompt", "correct_answer"):
            if not str(question.get(field, "")).strip():
                raise ValueError(f"English question is missing {field}")
        if question.get("type") != mode:
            raise ValueError(f"English question {question['question_id']} has wrong mode")
        options = question.get("options")
        correct_index = question.get("correct_index")
        if not isinstance(options, list) or len(options) != 4 or len(set(options)) != 4:
            raise ValueError(
                f"English question {question['question_id']} needs four unique options"
            )
        if not isinstance(correct_index, int) or not 0 <= correct_index < 4:
            raise ValueError(f"English question {question['question_id']} has invalid key")
        if options[correct_index] != question["correct_answer"]:
            raise ValueError(f"English question {question['question_id']} key does not match")

    def level(self, level_code: str) -> dict[str, Any]:
        try:
            return self._levels[level_code]
        except KeyError as exc:
            raise EnglishVocabularyNotFoundError("Уровень английского не найден") from exc

    def level_ids(self) -> tuple[str, ...]:
        return tuple(self._levels)

    def levels(self) -> list[dict[str, Any]]:
        return [
            {
                "code": level["code"],
                "order": int(level["order"]),
                "name": level["name"],
                "cefr": level["cefr"],
                "descriptor": level["descriptor"],
                "color": level["color"],
                "word_count": 80,
                "units": level["units"],
            }
            for level in self._levels.values()
        ]

    def question(self, question_id: str) -> dict[str, Any]:
        try:
            return self._questions[question_id]
        except KeyError as exc:
            raise EnglishVocabularyNotFoundError("Вопрос английского не найден") from exc

    def question_ids(self, level_code: str, mode: str) -> tuple[str, ...]:
        self.level(level_code)
        if mode not in TEST_MODES:
            raise EnglishVocabularyError("Неизвестный режим английского")
        return tuple(self._question_ids[(level_code, mode)])

    def round_question_ids(
        self,
        *,
        level_code: str,
        mode: str,
        seen_ids: set[str],
        limit: int = 10,
    ) -> tuple[str, ...]:
        all_ids = list(self.question_ids(level_code, mode))
        unseen = [question_id for question_id in all_ids if question_id not in seen_ids]
        seen = [question_id for question_id in all_ids if question_id in seen_ids]
        random.SystemRandom().shuffle(unseen)
        random.SystemRandom().shuffle(seen)
        return tuple((unseen + seen)[:limit])

    def public_question(
        self,
        question_id: str,
        *,
        position: int,
        total: int,
    ) -> dict[str, Any]:
        question = self.question(question_id)
        return {
            "id": question_id,
            "word_id": question["word_id"],
            "type": question["type"],
            "instruction": question["instruction"],
            "prompt": question["prompt"],
            "level_code": question["level_code"],
            "level": question["level"],
            "cefr": question["cefr"],
            "unit": int(question["unit"]),
            "theme": question["theme_ru"],
            "position": position,
            "total": total,
            "options": [
                {"id": chr(65 + index), "text": text}
                for index, text in enumerate(question["options"])
            ],
        }

    def answer(self, question_id: str, option_id: str) -> dict[str, Any]:
        question = self.question(question_id)
        if option_id not in {"A", "B", "C", "D"}:
            raise EnglishVocabularyInvalidOptionError("Выберите один из четырёх вариантов")
        selected_index = ord(option_id) - 65
        correct_index = int(question["correct_index"])
        correct_answer = str(question["correct_answer"])
        if question["type"] == "en_to_ru":
            explanation = f"{question['prompt']} переводится как «{correct_answer}»."
        elif question["type"] == "spelling":
            explanation = f"{correct_answer} — правильное написание слова «{question['prompt']}»."
        else:
            explanation = f"«{question['prompt']}» по-английски — {correct_answer}."
        return {
            "is_correct": selected_index == correct_index,
            "correct_option_id": chr(65 + correct_index),
            "correct_answer": correct_answer,
            "explanation": explanation,
        }


class EnglishVocabularyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_session(self, *, user_id: int, session_id: str) -> dict[str, Any] | None:
        row = await self.database.read_one(
            "SELECT * FROM english_vocabulary_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        return self._session_from_row(row) if row else None

    async def active_review(self, *, user_id: int) -> dict[str, Any] | None:
        row = await self.database.read_one(
            """
            SELECT * FROM english_vocabulary_sessions
            WHERE user_id = ? AND is_review = 1 AND status = 'active'
            ORDER BY started_at DESC LIMIT 1
            """,
            (user_id,),
        )
        return self._session_from_row(row) if row else None

    async def seen_question_ids(self, *, user_id: int, level_code: str, mode: str) -> set[str]:
        rows = await self.database.read_all(
            """
            SELECT DISTINCT a.question_id
            FROM english_vocabulary_answers a
            JOIN english_vocabulary_sessions s ON s.id = a.session_id
            WHERE a.user_id = ? AND s.level_code = ? AND s.mode = ? AND s.is_review = 0
            """,
            (user_id, level_code, mode),
        )
        return {str(row["question_id"]) for row in rows}

    async def start(
        self,
        *,
        user_id: int,
        level_code: str,
        mode: str,
        question_ids: tuple[str, ...],
        is_review: bool = False,
    ) -> dict[str, Any]:
        review_flag = int(is_review)

        def operation(connection: sqlite3.Connection) -> str:
            active = connection.execute(
                """
                SELECT id FROM english_vocabulary_sessions
                WHERE user_id = ? AND level_code = ? AND mode = ?
                  AND is_review = ? AND status = 'active'
                ORDER BY started_at DESC LIMIT 1
                """,
                (user_id, level_code, mode, review_flag),
            ).fetchone()
            if active:
                return str(active["id"])
            session_id = uuid.uuid4().hex
            connection.execute(
                """
                INSERT INTO english_vocabulary_sessions(
                    id, user_id, level_code, mode, is_review, question_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, level_code, mode, review_flag, json.dumps(question_ids)),
            )
            return session_id

        session_id = await self.database.write(operation)
        session = await self.get_session(user_id=user_id, session_id=session_id)
        assert session is not None
        return session

    async def due_question_ids(self, *, user_id: int, limit: int = 10) -> tuple[str, ...]:
        rows = await self.database.read_all(
            """
            SELECT question_id FROM english_vocabulary_reviews
            WHERE user_id = ? AND active = 1 AND next_due_at <= CURRENT_TIMESTAMP
            ORDER BY next_due_at, updated_at LIMIT ?
            """,
            (user_id, limit),
        )
        return tuple(str(row["question_id"]) for row in rows)

    async def due_count(self, *, user_id: int) -> int:
        row = await self.database.read_one(
            """
            SELECT COUNT(*) AS amount FROM english_vocabulary_reviews
            WHERE user_id = ? AND active = 1 AND next_due_at <= CURRENT_TIMESTAMP
            """,
            (user_id,),
        )
        return int(row["amount"]) if row else 0

    async def progress(self, *, user_id: int) -> dict[tuple[str, str], dict[str, int]]:
        rows = await self.database.read_all(
            """
            SELECT level_code, mode,
                   COUNT(*) AS rounds,
                   MAX(correct_count) AS best_correct,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_rounds
            FROM english_vocabulary_sessions
            WHERE user_id = ? AND is_review = 0
            GROUP BY level_code, mode
            """,
            (user_id,),
        )
        return {
            (str(row["level_code"]), str(row["mode"])): {
                "rounds": int(row["rounds"]),
                "completed_rounds": int(row["completed_rounds"]),
                "best_correct": int(row["best_correct"] or 0),
            }
            for row in rows
        }

    async def answer(
        self,
        *,
        user_id: int,
        session_id: str,
        question_id: str,
        option_id: str,
        is_correct: bool,
    ) -> EnglishAnswerResult:
        def operation(connection: sqlite3.Connection) -> EnglishAnswerResult:
            row = connection.execute(
                "SELECT * FROM english_vocabulary_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if row is None:
                raise EnglishVocabularyNotFoundError("Раунд английского не найден")
            if row["status"] != "active":
                raise EnglishVocabularyStaleAnswerError("Этот раунд уже завершён")
            question_ids = json.loads(row["question_ids_json"])
            position = int(row["current_position"])
            if position >= len(question_ids) or question_ids[position] != question_id:
                raise EnglishVocabularyStaleAnswerError("Этот вопрос уже отвечен")

            points = 10 if is_correct else -2
            current_streak = int(row["current_streak"]) + 1 if is_correct else 0
            best_streak = max(int(row["best_streak"]), current_streak)
            correct_count = int(row["correct_count"]) + int(is_correct)
            next_position = position + 1
            finished = next_position >= len(question_ids)
            connection.execute(
                """
                INSERT INTO english_vocabulary_answers(
                    session_id, user_id, question_id, position, selected_option_id,
                    is_correct, points_awarded
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, question_id, position, option_id, int(is_correct), points),
            )
            connection.execute(
                """
                UPDATE english_vocabulary_sessions SET
                    current_position = ?, correct_count = ?, points = points + ?,
                    current_streak = ?, best_streak = ?,
                    status = CASE WHEN ? THEN 'completed' ELSE 'active' END,
                    completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    next_position,
                    correct_count,
                    points,
                    current_streak,
                    best_streak,
                    int(finished),
                    int(finished),
                    session_id,
                ),
            )
            if is_correct and int(row["is_review"]):
                review = connection.execute(
                    """
                    SELECT stage FROM english_vocabulary_reviews
                    WHERE user_id = ? AND question_id = ?
                    """,
                    (user_id, question_id),
                ).fetchone()
                if review:
                    stage = int(review["stage"])
                    if stage >= len(REVIEW_INTERVALS) - 1:
                        connection.execute(
                            """
                            UPDATE english_vocabulary_reviews
                            SET active = 0, next_due_at = NULL, updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ? AND question_id = ?
                            """,
                            (user_id, question_id),
                        )
                    else:
                        next_stage = stage + 1
                        modifier = f"+{REVIEW_INTERVALS[next_stage]} days"
                        connection.execute(
                            """
                            UPDATE english_vocabulary_reviews
                            SET stage = ?, next_due_at = datetime('now', ?),
                                updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ? AND question_id = ?
                            """,
                            (next_stage, modifier, user_id, question_id),
                        )
            elif not is_correct:
                connection.execute(
                    """
                    INSERT INTO english_vocabulary_reviews(
                        user_id, question_id, level_code, mode, stage, next_due_at, active
                    ) VALUES (?, ?, ?, ?, 0, datetime('now', '+1 day'), 1)
                    ON CONFLICT(user_id, question_id) DO UPDATE SET
                        stage = 0,
                        next_due_at = datetime('now', '+1 day'),
                        active = 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, question_id, row["level_code"], row["mode"]),
                )

            return EnglishAnswerResult(
                session_id=session_id,
                question_id=question_id,
                position=position,
                total=len(question_ids),
                is_correct=is_correct,
                points=points,
                correct_count=correct_count,
                current_streak=current_streak,
                best_streak=best_streak,
                finished=finished,
            )

        return await self.database.write(operation)

    @staticmethod
    def summary(session: dict[str, Any]) -> dict[str, Any]:
        total = len(session["question_ids"])
        correct = int(session["correct_count"])
        return {
            "correct_count": correct,
            "questions_total": total,
            "percent": round(correct * 100 / total),
            "points": int(session["points"]),
            "best_streak": int(session["best_streak"]),
            "is_review": bool(session["is_review"]),
        }

    @staticmethod
    def _session_from_row(row: sqlite3.Row) -> dict[str, Any]:
        payload = dict(row)
        payload["question_ids"] = json.loads(payload.pop("question_ids_json"))
        payload["is_review"] = bool(payload["is_review"])
        return payload
