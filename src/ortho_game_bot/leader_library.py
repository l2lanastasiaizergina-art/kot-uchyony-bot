from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ortho_game_bot.database.connection import Database


class LeaderLibraryError(RuntimeError):
    """Base error for the interactive leader library."""


class LeaderBookNotFoundError(LeaderLibraryError):
    pass


class LeaderLibraryStaleAnswerError(LeaderLibraryError):
    pass


class LeaderLibraryInvalidOptionError(LeaderLibraryError):
    pass


@dataclass(frozen=True, slots=True)
class LibraryAnswerResult:
    book_id: str
    step_index: int
    attempt_number: int
    selected_option: int
    correct_option: int
    correct_answer: str
    is_correct: bool
    allow_retry: bool
    step_completed: bool
    mission_completed: bool
    first_attempt_correct: int
    points: int


class LeaderLibraryContent:
    """Loads and validates the authored book missions."""

    CORE_STEP_COUNT = 8

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.product = str(payload.get("product", "Библиотека лидера"))
        self.subtitle = str(payload.get("subtitle", "100 книг — 600 решений"))
        raw_books = payload.get("books")
        if not isinstance(raw_books, list) or not raw_books:
            raise ValueError("Пакет Библиотеки лидера не содержит книг")
        self._books: dict[str, dict[str, Any]] = {}
        for raw_book in raw_books:
            self._validate_book(raw_book)
            book_id = str(raw_book["book_id"])
            if book_id in self._books:
                raise ValueError(f"Повторяется book_id {book_id}")
            self._books[book_id] = raw_book

    @staticmethod
    def _validate_question(question: Any, label: str) -> None:
        if not isinstance(question, dict):
            raise ValueError(f"{label}: вопрос должен быть объектом")
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"{label}: требуется четыре варианта ответа")
        correct = question.get("correct_option")
        if not isinstance(correct, int) or not 0 <= correct < 4:
            raise ValueError(f"{label}: неверный correct_option")
        if not str(question.get("prompt", "")).strip():
            raise ValueError(f"{label}: нет формулировки вопроса")
        if not str(question.get("explanation", "")).strip():
            raise ValueError(f"{label}: нет объяснения")

    @classmethod
    def _validate_book(cls, book: Any) -> None:
        if not isinstance(book, dict):
            raise ValueError("Книга должна быть объектом")
        for field in ("book_id", "title", "author", "mission_title", "hook"):
            if not str(book.get(field, "")).strip():
                raise ValueError(f"Книга: не заполнено поле {field}")
        episodes = book.get("episodes")
        if not isinstance(episodes, list) or len(episodes) != 6:
            raise ValueError(f"Книга {book['book_id']}: требуется шесть эпизодов")
        for index, episode in enumerate(episodes):
            if not str(episode.get("text", "")).strip():
                raise ValueError(f"Книга {book['book_id']}, эпизод {index + 1}: нет текста")
            cls._validate_question(
                episode.get("question"),
                f"Книга {book['book_id']}, эпизод {index + 1}",
            )
        cls._validate_question(book.get("critical_filter"), f"Книга {book['book_id']}, фильтр")
        final_case = book.get("final_case")
        if not isinstance(final_case, dict) or not str(final_case.get("text", "")).strip():
            raise ValueError(f"Книга {book['book_id']}: нет финального кейса")
        cls._validate_question(final_case, f"Книга {book['book_id']}, финал")
        cls._validate_question(book.get("review_24h"), f"Книга {book['book_id']}, 24h")
        cls._validate_question(book.get("review_7d"), f"Книга {book['book_id']}, 7d")

    def book(self, book_id: str) -> dict[str, Any]:
        try:
            return self._books[book_id]
        except KeyError as exc:
            raise LeaderBookNotFoundError("Книга не найдена") from exc

    def book_ids(self) -> tuple[str, ...]:
        return tuple(self._books)

    def step(self, book_id: str, step_index: int) -> dict[str, Any]:
        book = self.book(book_id)
        if not 0 <= step_index < self.CORE_STEP_COUNT:
            raise LeaderLibraryStaleAnswerError("Этот этап уже завершён")
        if step_index < 6:
            episode = book["episodes"][step_index]
            return {
                "kind": "episode",
                "title": f"Эпизод {step_index + 1}",
                "eyebrow": episode["principle"],
                "text": episode["text"],
                "question": episode["question"],
            }
        if step_index == 6:
            return {
                "kind": "critical_filter",
                "title": "Критический фильтр",
                "eyebrow": "Где заканчивается полезная идея?",
                "text": "Проверь, не превратился ли принцип книги в слишком простой лозунг.",
                "question": book["critical_filter"],
            }
        return {
            "kind": "final_case",
            "title": "Финальное решение",
            "eyebrow": "Собери идеи книги вместе",
            "text": book["final_case"]["text"],
            "question": book["final_case"],
        }

    @staticmethod
    def public_question(question: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": question.get("type", "application"),
            "prompt": question["prompt"],
            "options": question["options"],
        }

    def public_step(self, book_id: str, step_index: int) -> dict[str, Any]:
        step = self.step(book_id, step_index)
        return {
            **{key: value for key, value in step.items() if key != "question"},
            "step_index": step_index,
            "step_total": self.CORE_STEP_COUNT,
            "question": self.public_question(step["question"]),
        }

    def summaries(self) -> list[dict[str, Any]]:
        return [
            {
                "book_id": book["book_id"],
                "title": book["title"],
                "author": book["author"],
                "mission_title": book["mission_title"],
                "thematic_block": book["thematic_block"],
            }
            for book in self._books.values()
        ]

    def answer_payload(
        self, book_id: str, step_index: int, selected_option: int
    ) -> tuple[dict[str, Any], bool]:
        if not 0 <= selected_option < 4:
            raise LeaderLibraryInvalidOptionError("Выберите один из четырёх вариантов")
        question = self.step(book_id, step_index)["question"]
        return question, selected_option == question["correct_option"]

    def review(self, book_id: str, review_kind: str) -> dict[str, Any]:
        book = self.book(book_id)
        key = {"24h": "review_24h", "7d": "review_7d"}.get(review_kind)
        if key is None:
            raise LeaderLibraryError("Неизвестный вид повторения")
        return book[key]


class LeaderLibraryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def ensure_started(self, *, user_id: int, book_id: str) -> dict[str, Any]:
        def operation(connection: sqlite3.Connection) -> None:
            user = connection.execute(
                "SELECT 1 FROM users WHERE telegram_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                raise LookupError("Пользователь не найден")
            connection.execute(
                """
                INSERT INTO leader_library_progress(user_id, book_id)
                VALUES (?, ?)
                ON CONFLICT(user_id, book_id) DO NOTHING
                """,
                (user_id, book_id),
            )

        await self.database.write(operation)
        progress = await self.get(user_id=user_id, book_id=book_id)
        assert progress is not None
        return progress

    async def get(self, *, user_id: int, book_id: str) -> dict[str, Any] | None:
        row = await self.database.read_one(
            """
            SELECT user_id, book_id, current_step, first_attempt_correct, answers_count,
                   status, started_at, updated_at, completed_at,
                   review_24h_answered_at, review_7d_answered_at
            FROM leader_library_progress
            WHERE user_id = ? AND book_id = ?
            """,
            (user_id, book_id),
        )
        return dict(row) if row else None

    async def all_for_user(self, *, user_id: int) -> dict[str, dict[str, Any]]:
        rows = await self.database.read_all(
            """
            SELECT user_id, book_id, current_step, first_attempt_correct, answers_count,
                   status, started_at, updated_at, completed_at,
                   review_24h_answered_at, review_7d_answered_at
            FROM leader_library_progress
            WHERE user_id = ?
            ORDER BY book_id
            """,
            (user_id,),
        )
        return {str(row["book_id"]): dict(row) for row in rows}

    async def attempt_count(self, *, user_id: int, book_id: str, step_index: int) -> int:
        row = await self.database.read_one(
            """
            SELECT COUNT(*) AS amount
            FROM leader_library_answers
            WHERE user_id = ? AND book_id = ? AND step_index = ?
            """,
            (user_id, book_id, step_index),
        )
        return int(row["amount"]) if row else 0

    async def answer(
        self,
        *,
        user_id: int,
        book_id: str,
        step_index: int,
        selected_option: int,
        correct_option: int,
        total_steps: int,
    ) -> LibraryAnswerResult:
        if not 0 <= selected_option < 4:
            raise LeaderLibraryInvalidOptionError("Выберите один из четырёх вариантов")

        def operation(connection: sqlite3.Connection) -> LibraryAnswerResult:
            row = connection.execute(
                """
                SELECT current_step, first_attempt_correct, status
                FROM leader_library_progress
                WHERE user_id = ? AND book_id = ?
                """,
                (user_id, book_id),
            ).fetchone()
            if row is None:
                raise LeaderLibraryStaleAnswerError("Сначала откройте книгу")
            if row["status"] == "completed" or row["current_step"] != step_index:
                raise LeaderLibraryStaleAnswerError("Этот ответ уже сохранён")

            attempt_row = connection.execute(
                """
                SELECT COUNT(*) AS amount
                FROM leader_library_answers
                WHERE user_id = ? AND book_id = ? AND step_index = ?
                """,
                (user_id, book_id, step_index),
            ).fetchone()
            attempt_number = int(attempt_row["amount"]) + 1
            if attempt_number > 2:
                raise LeaderLibraryStaleAnswerError("Попытки для этого вопроса завершены")

            is_correct = selected_option == correct_option
            step_completed = is_correct or attempt_number == 2
            mission_completed = step_completed and step_index + 1 >= total_steps
            first_attempt_delta = int(is_correct and attempt_number == 1)
            points = 10 if first_attempt_delta else 0
            connection.execute(
                """
                INSERT INTO leader_library_answers(
                    user_id, book_id, step_index, attempt_number,
                    selected_option, is_correct, points_awarded
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    book_id,
                    step_index,
                    attempt_number,
                    selected_option,
                    int(is_correct),
                    points,
                ),
            )
            connection.execute(
                """
                UPDATE leader_library_progress SET
                    current_step = CASE WHEN ? THEN ? ELSE current_step END,
                    first_attempt_correct = first_attempt_correct + ?,
                    answers_count = answers_count + 1,
                    status = CASE WHEN ? THEN 'completed' ELSE status END,
                    completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND book_id = ?
                """,
                (
                    int(step_completed),
                    min(total_steps, step_index + 1),
                    first_attempt_delta,
                    int(mission_completed),
                    int(mission_completed),
                    user_id,
                    book_id,
                ),
            )
            return LibraryAnswerResult(
                book_id=book_id,
                step_index=step_index,
                attempt_number=attempt_number,
                selected_option=selected_option,
                correct_option=correct_option,
                correct_answer="",
                is_correct=is_correct,
                allow_retry=not is_correct and attempt_number == 1,
                step_completed=step_completed,
                mission_completed=mission_completed,
                first_attempt_correct=int(row["first_attempt_correct"]) + first_attempt_delta,
                points=points,
            )

        return await self.database.write(operation)

    async def record_review(
        self,
        *,
        user_id: int,
        book_id: str,
        review_kind: str,
        selected_option: int,
        correct_option: int,
    ) -> dict[str, Any]:
        if review_kind not in {"24h", "7d"}:
            raise LeaderLibraryError("Неизвестный вид повторения")
        if not 0 <= selected_option < 4:
            raise LeaderLibraryInvalidOptionError("Выберите один из четырёх вариантов")

        column = "review_24h_answered_at" if review_kind == "24h" else "review_7d_answered_at"

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            progress = connection.execute(
                """
                SELECT completed_at, review_24h_answered_at, review_7d_answered_at
                FROM leader_library_progress
                WHERE user_id = ? AND book_id = ? AND status = 'completed'
                """,
                (user_id, book_id),
            ).fetchone()
            if progress is None:
                raise LeaderLibraryStaleAnswerError("Сначала завершите книгу")
            if progress[column] is not None:
                raise LeaderLibraryStaleAnswerError("Это повторение уже пройдено")
            completed_at = _parse_sqlite_datetime(progress["completed_at"])
            wait = timedelta(days=1 if review_kind == "24h" else 7)
            if datetime.now(timezone.utc) < completed_at + wait:
                raise LeaderLibraryStaleAnswerError("Повторение ещё не открылось")
            is_correct = selected_option == correct_option
            connection.execute(
                """
                INSERT INTO leader_library_review_answers(
                    user_id, book_id, review_kind, selected_option, is_correct
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, book_id, review_kind, selected_option, int(is_correct)),
            )
            connection.execute(
                f"""
                UPDATE leader_library_progress
                SET {column} = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND book_id = ?
                """,
                (user_id, book_id),
            )
            return {
                "book_id": book_id,
                "review_kind": review_kind,
                "selected_option": selected_option,
                "correct_option": correct_option,
                "is_correct": is_correct,
            }

        return await self.database.write(operation)


def _parse_sqlite_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def review_due(progress: dict[str, Any], *, now: datetime | None = None) -> str | None:
    if progress.get("status") != "completed" or not progress.get("completed_at"):
        return None
    current = now or datetime.now(timezone.utc)
    completed = _parse_sqlite_datetime(str(progress["completed_at"]))
    if not progress.get("review_24h_answered_at") and current >= completed + timedelta(days=1):
        return "24h"
    if not progress.get("review_7d_answered_at") and current >= completed + timedelta(days=7):
        return "7d"
    return None
