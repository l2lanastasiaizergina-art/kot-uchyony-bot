from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ortho_game_bot.utils.text import normalize_answer
from ortho_game_bot.utils.time import period_key

from .connection import Database
from .models import GameWord, LeaderboardEntry, ScoreApplication, User


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        telegram_id=row["telegram_id"],
        username=row["username"],
        display_name=row["display_name"],
        grade=row["grade"],
        total_score=row["total_score"],
        monthly_score=row["monthly_score"],
        monthly_period=row["monthly_period"],
        games_played=row["games_played"],
        correct_answers=row["correct_answers"],
        wrong_answers=row["wrong_answers"],
        current_streak=row["current_streak"],
        best_streak=row["best_streak"],
        daily_streak=row["daily_streak"],
        longest_daily_streak=row["longest_daily_streak"],
        last_qualifying_date=row["last_qualifying_date"],
        timezone_name=row["timezone_name"],
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


class UserRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def register_or_update(
        self, telegram_id: int, username: str | None, display_name: str
    ) -> User:
        current_period = period_key()

        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO users(telegram_id, username, display_name, monthly_period)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    username = excluded.username,
                    display_name = excluded.display_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (telegram_id, username, display_name, current_period),
            )
            connection.execute(
                """
                INSERT INTO monthly_scores(user_id, period_key)
                VALUES (?, ?)
                ON CONFLICT(user_id, period_key) DO NOTHING
                """,
                (telegram_id, current_period),
            )

        await self.database.write(operation)
        user = await self.get(telegram_id)
        assert user is not None
        return user

    async def get(self, telegram_id: int) -> User | None:
        row = await self.database.read_one(
            "SELECT * FROM users WHERE telegram_id = ? AND is_active = 1", (telegram_id,)
        )
        return _user_from_row(row) if row else None

    async def set_grade(self, telegram_id: int, grade: int) -> User:
        if not 1 <= grade <= 11:
            raise ValueError("Класс должен быть от 1 до 11")

        def operation(connection: sqlite3.Connection) -> None:
            cursor = connection.execute(
                "UPDATE users SET grade = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (grade, telegram_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("Пользователь не найден")

        await self.database.write(operation)
        user = await self.get(telegram_id)
        assert user is not None
        return user

    async def apply_score(
        self,
        *,
        telegram_id: int,
        source_type: str,
        source_id: str,
        delta: int,
        idempotency_key: str,
        correct_delta: int = 0,
        wrong_delta: int = 0,
        games_delta: int = 0,
        streak_after: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> ScoreApplication:
        current_period = period_key()

        def operation(connection: sqlite3.Connection) -> ScoreApplication:
            user = connection.execute(
                "SELECT total_score, best_streak FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
            if user is None:
                raise LookupError("Пользователь не найден")

            monthly = connection.execute(
                "SELECT score FROM monthly_scores WHERE user_id = ? AND period_key = ?",
                (telegram_id, current_period),
            ).fetchone()
            old_monthly = monthly["score"] if monthly else 0
            new_total = max(0, user["total_score"] + delta)
            new_monthly = max(0, old_monthly + delta)
            effective_total_delta = new_total - user["total_score"]
            effective_monthly_delta = new_monthly - old_monthly

            event_cursor = connection.execute(
                """
                INSERT OR IGNORE INTO score_events(
                    id, user_id, source_type, source_id, delta_total, delta_monthly,
                    period_key, idempotency_key, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    telegram_id,
                    source_type,
                    source_id,
                    effective_total_delta,
                    effective_monthly_delta,
                    current_period,
                    idempotency_key,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            if event_cursor.rowcount == 0:
                return ScoreApplication(False, user["total_score"], old_monthly)

            connection.execute(
                """
                INSERT INTO monthly_scores(
                    user_id, period_key, score, games_played, correct_answers, wrong_answers
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, period_key) DO UPDATE SET
                    score = excluded.score,
                    games_played = monthly_scores.games_played + excluded.games_played,
                    correct_answers = monthly_scores.correct_answers + excluded.correct_answers,
                    wrong_answers = monthly_scores.wrong_answers + excluded.wrong_answers,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    telegram_id,
                    current_period,
                    new_monthly,
                    games_delta,
                    correct_delta,
                    wrong_delta,
                ),
            )
            connection.execute(
                """
                UPDATE users SET
                    total_score = ?, monthly_score = ?, monthly_period = ?,
                    games_played = games_played + ?,
                    correct_answers = correct_answers + ?,
                    wrong_answers = wrong_answers + ?,
                    current_streak = ?,
                    best_streak = MAX(best_streak, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
                """,
                (
                    new_total,
                    new_monthly,
                    current_period,
                    games_delta,
                    correct_delta,
                    wrong_delta,
                    streak_after,
                    streak_after,
                    telegram_id,
                ),
            )
            return ScoreApplication(True, new_total, new_monthly)

        return await self.database.write(operation)

    async def leaderboard(
        self, *, scope: str = "global", grade: int | None = None, limit: int = 10
    ) -> list[LeaderboardEntry]:
        if not 1 <= limit <= 100:
            raise ValueError("limit должен быть от 1 до 100")
        params: list[Any] = []
        where = "u.is_active = 1"
        if grade is not None:
            if not 1 <= grade <= 11:
                raise ValueError("Класс должен быть от 1 до 11")
            where += " AND u.grade = ?"
            params.append(grade)

        if scope == "monthly":
            params.insert(0, period_key())
            score_expression = "COALESCE(ms.score, 0)"
            join = "LEFT JOIN monthly_scores ms ON ms.user_id = u.telegram_id AND ms.period_key = ?"
        elif scope == "global":
            score_expression = "u.total_score"
            join = ""
        else:
            raise ValueError("scope должен быть global или monthly")

        params.append(limit)
        rows = await self.database.read_all(
            f"""
            SELECT u.telegram_id, u.username, u.display_name, u.grade,
                   {score_expression} AS score
            FROM users u
            {join}
            WHERE {where}
            ORDER BY score DESC, u.correct_answers DESC, u.telegram_id ASC
            LIMIT ?
            """,
            params,
        )
        return [
            LeaderboardEntry(
                position=index,
                telegram_id=row["telegram_id"],
                username=row["username"],
                display_name=row["display_name"],
                grade=row["grade"],
                score=row["score"],
            )
            for index, row in enumerate(rows, start=1)
        ]


class ContentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def import_file(self, path: Path) -> tuple[int, int]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._validate_payload(payload)
        canonical_json = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        checksum = hashlib.sha256(canonical_json).hexdigest()

        def operation(connection: sqlite3.Connection) -> tuple[int, int]:
            same_version = connection.execute(
                "SELECT id, checksum FROM content_packs WHERE slug = ? AND version = ?",
                (payload["slug"], payload["version"]),
            ).fetchone()
            if same_version:
                if same_version["checksum"] != checksum:
                    raise ValueError(
                        f"Пакет {payload['slug']} v{payload['version']} "
                        "изменён без повышения версии"
                    )
                return same_version["id"], 0

            connection.execute(
                "UPDATE content_packs SET is_active = 0 WHERE slug = ?", (payload["slug"],)
            )
            pack_cursor = connection.execute(
                """
                INSERT INTO content_packs(slug, grade, title, source_name, version, checksum)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["slug"],
                    payload["grade"],
                    payload["title"],
                    payload.get("source"),
                    payload["version"],
                    checksum,
                ),
            )
            pack_id = int(pack_cursor.lastrowid)
            for word in payload["words"]:
                connection.execute(
                    """
                    INSERT INTO words(
                        pack_id, external_id, grade, group_name, rule_text, word,
                        normalized_answer, prompt_text, orthograms_json,
                        distractors_json, tags_json, difficulty
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pack_id,
                        word["id"],
                        payload["grade"],
                        word["group"],
                        word.get("rule"),
                        word["answer"],
                        normalize_answer(word["answer"]),
                        word.get("prompt"),
                        json.dumps(word.get("orthograms", []), ensure_ascii=False),
                        json.dumps(word.get("distractors", []), ensure_ascii=False),
                        json.dumps(word.get("tags", []), ensure_ascii=False),
                        word.get("difficulty", 1),
                    ),
                )
            return pack_id, len(payload["words"])

        return await self.database.write(operation)

    async def import_directory(self, directory: Path) -> int:
        imported = 0
        for path in sorted(directory.glob("grade_*.json")):
            _, count = await self.import_file(path)
            imported += count
        return imported

    async def counts_by_grade(self) -> dict[int, int]:
        rows = await self.database.read_all(
            """
            SELECT w.grade, COUNT(*) AS amount
            FROM words w
            JOIN content_packs p ON p.id = w.pack_id
            WHERE w.is_active = 1 AND p.is_active = 1
            GROUP BY w.grade ORDER BY w.grade
            """
        )
        return {row["grade"]: row["amount"] for row in rows}

    async def sample_words(self, *, grade: int, limit: int) -> list[GameWord]:
        if not 1 <= grade <= 11:
            raise ValueError("Класс должен быть от 1 до 11")
        if not 1 <= limit <= 30:
            raise ValueError("Количество заданий должно быть от 1 до 30")
        rows = await self.database.read_all(
            """
            SELECT w.id, w.external_id, w.grade, w.group_name, w.rule_text,
                   w.word, w.orthograms_json
            FROM words w
            JOIN content_packs p ON p.id = w.pack_id
            WHERE w.grade = ? AND w.is_active = 1 AND p.is_active = 1
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (grade, limit),
        )
        result = [
            GameWord(
                id=row["id"],
                external_id=row["external_id"],
                grade=row["grade"],
                group_name=row["group_name"],
                rule_text=row["rule_text"],
                answer=row["word"],
                orthograms=tuple(json.loads(row["orthograms_json"])),
            )
            for row in rows
        ]
        random.shuffle(result)
        return result

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> None:
        required = {"slug", "version", "grade", "title", "words"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"В пакете отсутствуют поля: {', '.join(sorted(missing))}")
        if not 1 <= int(payload["grade"]) <= 11:
            raise ValueError("grade должен быть от 1 до 11")
        if not payload["words"]:
            raise ValueError("Пакет слов не может быть пустым")
        seen: set[str] = set()
        for word in payload["words"]:
            for key in ("id", "group", "answer"):
                if not str(word.get(key, "")).strip():
                    raise ValueError(f"У слова отсутствует обязательное поле {key}")
            if word["id"] in seen:
                raise ValueError(f"Повторяющийся id: {word['id']}")
            seen.add(word["id"])
