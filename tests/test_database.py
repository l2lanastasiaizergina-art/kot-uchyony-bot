from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ortho_game_bot.database import ContentRepository, Database, UserRepository


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test.sqlite3")
        await self.db.migrate()
        self.users = UserRepository(self.db)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_register_grade_and_idempotent_score(self) -> None:
        user = await self.users.register_or_update(1001, "masha", "Маша")
        self.assertIsNone(user.grade)
        user = await self.users.set_grade(1001, 4)
        self.assertEqual(user.grade, 4)

        first = await self.users.apply_score(
            telegram_id=1001,
            source_type="game",
            source_id="game-1",
            delta=12,
            idempotency_key="game-1:q1",
            correct_delta=1,
            streak_after=3,
        )
        duplicate = await self.users.apply_score(
            telegram_id=1001,
            source_type="game",
            source_id="game-1",
            delta=12,
            idempotency_key="game-1:q1",
            correct_delta=1,
            streak_after=3,
        )
        self.assertTrue(first.applied)
        self.assertFalse(duplicate.applied)
        self.assertEqual((await self.users.get(1001)).total_score, 12)

    async def test_leaderboard(self) -> None:
        for user_id, name, score in ((1, "Аня", 10), (2, "Боря", 25), (3, "Вера", 15)):
            await self.users.register_or_update(user_id, None, name)
            await self.users.set_grade(user_id, 5)
            await self.users.apply_score(
                telegram_id=user_id,
                source_type="admin",
                source_id=f"seed-{user_id}",
                delta=score,
                idempotency_key=f"seed-{user_id}",
            )
        board = await self.users.leaderboard(grade=5)
        self.assertEqual([row.display_name for row in board], ["Боря", "Вера", "Аня"])

    async def test_content_import_is_repeatable(self) -> None:
        pack_path = Path(self.temp_dir.name) / "grade_01.json"
        pack_path.write_text(
            json.dumps(
                {
                    "slug": "grade-01-test",
                    "version": 1,
                    "grade": 1,
                    "title": "Тест",
                    "words": [
                        {"id": "g01-test", "group": "ЖИ—ШИ", "answer": "жираф"}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        repository = ContentRepository(self.db)
        _, first_count = await repository.import_file(pack_path)
        _, second_count = await repository.import_file(pack_path)
        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(await repository.counts_by_grade(), {1: 1})


if __name__ == "__main__":
    unittest.main()

