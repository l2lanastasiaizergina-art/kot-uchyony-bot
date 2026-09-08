from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ortho_game_bot.database import (
    ContentRepository,
    Database,
    GameRepository,
    StaleAnswerError,
    UserRepository,
)


class GameRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "game.sqlite3")
        await self.db.migrate()
        self.users = UserRepository(self.db)
        self.content = ContentRepository(self.db)
        self.games = GameRepository(self.db)
        await self.users.register_or_update(42, "kot", "Тестовый Кот")
        await self.users.set_grade(42, 3)

        pack_path = Path(self.temp_dir.name) / "grade_03.json"
        pack_path.write_text(
            json.dumps(
                {
                    "slug": "game-test",
                    "version": 1,
                    "grade": 3,
                    "title": "Игровой тест",
                    "words": [
                        {
                            "id": f"word-{index}",
                            "group": "Проверка",
                            "answer": f"слово{index}",
                        }
                        for index in range(10)
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        await self.content.import_file(pack_path)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def _start_round(self):
        words = await self.content.sample_words(grade=3, limit=10)
        return await self.games.create_choice_session(
            user_id=42,
            grade=3,
            questions=[
                (word, (word.answer, f"{word.answer}а", f"{word.answer}о", f"{word.answer}ь"))
                for word in words
            ],
        )

    async def test_complete_round_is_atomic_and_idempotent(self) -> None:
        yesterday = (
            datetime.now(ZoneInfo("Europe/Moscow")).date() - timedelta(days=1)
        ).isoformat()

        def seed_streak(connection):
            connection.execute(
                """
                UPDATE users
                SET daily_streak = 6, longest_daily_streak = 6, last_qualifying_date = ?
                WHERE telegram_id = 42
                """,
                (yesterday,),
            )

        await self.db.write(seed_streak)
        question = await self._start_round()
        session_id = question.session_id
        for position in range(10):
            outcome = await self.games.answer_choice(
                session_id=session_id,
                user_id=42,
                position=position,
                option_index=0,
            )
            self.assertEqual(outcome.finished, position == 9)

        snapshot = await self.games.round_snapshot(session_id=session_id, user_id=42)
        completion = await self.games.complete_round(session_id=session_id, user_id=42)
        duplicate = await self.games.complete_round(session_id=session_id, user_id=42)
        user = await self.users.get(42)

        self.assertEqual(snapshot.raw_score, 110)
        self.assertEqual(snapshot.correct_count, 10)
        self.assertTrue(completion.applied)
        self.assertEqual(completion.multiplier_percent, 200)
        self.assertEqual(completion.bonus_points, 110)
        self.assertEqual(completion.total_score, 220)
        self.assertFalse(duplicate.applied)
        self.assertIsNotNone(user)
        self.assertEqual(user.total_score, 220)
        self.assertEqual(user.games_played, 1)
        self.assertEqual(user.daily_streak, 7)

    async def test_duplicate_answer_rejected_and_error_scheduled(self) -> None:
        question = await self._start_round()
        outcome = await self.games.answer_choice(
            session_id=question.session_id,
            user_id=42,
            position=0,
            option_index=1,
        )
        self.assertFalse(outcome.is_correct)
        with self.assertRaises(StaleAnswerError):
            await self.games.answer_choice(
                session_id=question.session_id,
                user_id=42,
                position=0,
                option_index=1,
            )
        review = await self.db.read_one(
            "SELECT * FROM review_queue WHERE user_id = ? AND word_id = ?",
            (42, question.word_id),
        )
        self.assertIsNotNone(review)
        self.assertEqual(review["interval_days"], 1)
        self.assertEqual(review["last_answer_correct"], 0)


if __name__ == "__main__":
    unittest.main()
