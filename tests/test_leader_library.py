from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ortho_game_bot.database import Database, UserRepository
from ortho_game_bot.leader_library import (
    LeaderLibraryContent,
    LeaderLibraryRepository,
    LeaderLibraryStaleAnswerError,
    review_due,
)

CONTENT_PATH = Path(__file__).parents[1] / "data" / "leader_library" / "content.ru.json"


class LeaderLibraryContentTests(unittest.TestCase):
    def test_compiled_pack_contains_ten_complete_missions(self) -> None:
        content = LeaderLibraryContent(CONTENT_PATH)

        self.assertEqual(len(content.book_ids()), 10)
        self.assertEqual(content.book_ids()[0], "001")
        for book_id in content.book_ids():
            self.assertEqual(len(content.book(book_id)["episodes"]), 6)
            for step_index in range(content.CORE_STEP_COUNT):
                step = content.public_step(book_id, step_index)
                self.assertEqual(len(step["question"]["options"]), 4)
                self.assertNotIn("correct_option", step["question"])


class LeaderLibraryRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test.sqlite3")
        await self.db.migrate()
        self.users = UserRepository(self.db)
        await self.users.register_or_update(77, "reader", "Читатель")
        self.content = LeaderLibraryContent(CONTENT_PATH)
        self.progress = LeaderLibraryRepository(self.db)
        await self.progress.ensure_started(user_id=77, book_id="001")

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def answer_step(self, step_index: int, selected_option: int):
        question = self.content.step("001", step_index)["question"]
        return await self.progress.answer(
            user_id=77,
            book_id="001",
            step_index=step_index,
            selected_option=selected_option,
            correct_option=int(question["correct_option"]),
            total_steps=self.content.CORE_STEP_COUNT,
        )

    async def test_wrong_answer_allows_one_retry_then_advances(self) -> None:
        correct = int(self.content.step("001", 0)["question"]["correct_option"])
        first = await self.answer_step(0, (correct + 1) % 4)

        self.assertFalse(first.is_correct)
        self.assertTrue(first.allow_retry)
        self.assertFalse(first.step_completed)
        self.assertEqual((await self.progress.get(user_id=77, book_id="001"))["current_step"], 0)

        second = await self.answer_step(0, correct)
        self.assertTrue(second.is_correct)
        self.assertFalse(second.allow_retry)
        self.assertTrue(second.step_completed)
        self.assertEqual(second.points, 0)
        saved = await self.progress.get(user_id=77, book_id="001")
        self.assertEqual(saved["current_step"], 1)
        self.assertEqual(saved["answers_count"], 2)

        with self.assertRaises(LeaderLibraryStaleAnswerError):
            await self.answer_step(0, correct)

    async def test_first_try_points_completion_and_spaced_reviews(self) -> None:
        for step_index in range(self.content.CORE_STEP_COUNT):
            correct = int(self.content.step("001", step_index)["question"]["correct_option"])
            result = await self.answer_step(step_index, correct)
            self.assertEqual(result.points, 10)

        saved = await self.progress.get(user_id=77, book_id="001")
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["current_step"], 8)
        self.assertEqual(saved["first_attempt_correct"], 8)
        self.assertIsNone(review_due(saved))

        def age_completion(connection):
            connection.execute(
                """
                UPDATE leader_library_progress
                SET completed_at = datetime('now', '-8 days')
                WHERE user_id = 77 AND book_id = '001'
                """
            )

        await self.db.write(age_completion)
        aged = await self.progress.get(user_id=77, book_id="001")
        self.assertEqual(review_due(aged), "24h")

        review = self.content.review("001", "24h")
        result = await self.progress.record_review(
            user_id=77,
            book_id="001",
            review_kind="24h",
            selected_option=int(review["correct_option"]),
            correct_option=int(review["correct_option"]),
        )
        self.assertTrue(result["is_correct"])
        after_24h = await self.progress.get(user_id=77, book_id="001")
        self.assertEqual(review_due(after_24h), "7d")


if __name__ == "__main__":
    unittest.main()
