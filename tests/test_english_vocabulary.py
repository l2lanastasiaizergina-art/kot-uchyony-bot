from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ortho_game_bot.database import Database, UserRepository
from ortho_game_bot.english_vocabulary import (
    TEST_MODES,
    EnglishVocabularyContent,
    EnglishVocabularyRepository,
    EnglishVocabularyStaleAnswerError,
)

CONTENT_PATH = Path(__file__).parents[1] / "data" / "english_vocabulary" / "content.ru.json.gz"


class EnglishVocabularyContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = EnglishVocabularyContent(CONTENT_PATH)

    def test_pack_has_six_levels_and_three_complete_test_banks(self) -> None:
        self.assertEqual(len(self.content.level_ids()), 6)
        self.assertEqual(len(self.content.levels()), 6)
        for level_code in self.content.level_ids():
            for mode in TEST_MODES:
                self.assertEqual(len(self.content.question_ids(level_code, mode)), 80)

    def test_public_question_never_exposes_answer_key(self) -> None:
        question_id = self.content.question_ids("L1", "spelling")[0]
        question = self.content.public_question(question_id, position=0, total=10)
        self.assertEqual(len(question["options"]), 4)
        self.assertNotIn("correct_index", question)
        self.assertNotIn("correct_answer", question)
        self.assertTrue(all(set(option) == {"id", "text"} for option in question["options"]))

    def test_round_prefers_unseen_questions(self) -> None:
        all_ids = self.content.question_ids("L2", "ru_to_en")
        picked = self.content.round_question_ids(
            level_code="L2",
            mode="ru_to_en",
            seen_ids=set(all_ids[:70]),
        )
        self.assertEqual(set(picked), set(all_ids[70:]))


class EnglishVocabularyRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "english.sqlite3")
        await self.db.migrate()
        await UserRepository(self.db).register_or_update(77, "learner", "Ученик")
        self.content = EnglishVocabularyContent(CONTENT_PATH)
        self.repo = EnglishVocabularyRepository(self.db)

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_round_progress_and_spaced_review_cycle(self) -> None:
        question_ids = self.content.question_ids("L1", "en_to_ru")[:10]
        session = await self.repo.start(
            user_id=77,
            level_code="L1",
            mode="en_to_ru",
            question_ids=question_ids,
        )
        first_question = self.content.question(question_ids[0])
        correct_id = chr(65 + int(first_question["correct_index"]))
        wrong_id = next(letter for letter in "ABCD" if letter != correct_id)
        result = await self.repo.answer(
            user_id=77,
            session_id=session["id"],
            question_id=question_ids[0],
            option_id=wrong_id,
            is_correct=False,
        )
        self.assertEqual(result.points, -2)
        self.assertEqual(await self.repo.due_count(user_id=77), 0)

        def make_due(connection: sqlite3.Connection) -> None:
            connection.execute(
                "UPDATE english_vocabulary_reviews SET next_due_at = CURRENT_TIMESTAMP"
            )

        await self.db.write(make_due)
        self.assertEqual(await self.repo.due_question_ids(user_id=77), (question_ids[0],))
        review = await self.repo.start(
            user_id=77,
            level_code="REVIEW",
            mode="mixed",
            question_ids=(question_ids[0],),
            is_review=True,
        )
        review_result = await self.repo.answer(
            user_id=77,
            session_id=review["id"],
            question_id=question_ids[0],
            option_id=correct_id,
            is_correct=True,
        )
        self.assertTrue(review_result.finished)
        self.assertEqual(await self.repo.due_count(user_id=77), 0)
        with self.assertRaises(EnglishVocabularyStaleAnswerError):
            await self.repo.answer(
                user_id=77,
                session_id=review["id"],
                question_id=question_ids[0],
                option_id=correct_id,
                is_correct=True,
            )


if __name__ == "__main__":
    unittest.main()
