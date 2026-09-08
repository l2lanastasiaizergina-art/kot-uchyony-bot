from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ortho_game_bot.art_culture import (
    ArtCultureContent,
    ArtCultureRepository,
    ArtCultureStaleAnswerError,
)
from ortho_game_bot.database import Database, UserRepository

CONTENT_PATH = (
    Path(__file__).parents[1] / "data" / "art_culture" / "content.ru-en-kz.json.gz"
)


class ArtCultureContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = ArtCultureContent(CONTENT_PATH)

    def test_pack_has_complete_trilingual_visual_bank(self) -> None:
        self.assertEqual(len(self.content.module_ids()), 27)
        self.assertEqual(len(self.content.question_ids("M01", "child")), 15)
        for language in ("ru", "en", "kz"):
            module = self.content.localized_module("M01", language)
            self.assertTrue(module["title"])
            question = self.content.public_question(
                "Q0002",
                language=language,
                age_mode="teen",
                shuffle_seed="stable",
            )
            self.assertEqual(len(question["options"]), 4)
            self.assertTrue(all(option["image"] for option in question["options"]))
            self.assertTrue(all("is_correct" not in option for option in question["options"]))

    def test_age_modes_change_learning_order_without_removing_content(self) -> None:
        child = self.content.question_ids("M01", "child")
        adult = self.content.question_ids("M01", "adult")
        self.assertEqual(self.content.question(child[0])["level"], "2_VISUAL")
        self.assertEqual(self.content.question(adult[0])["level"], "1_FOUNDATION")
        self.assertEqual(set(child), set(adult))


class ArtCultureRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "art.sqlite3")
        await self.db.migrate()
        await UserRepository(self.db).register_or_update(88, "viewer", "Зритель")
        self.content = ArtCultureContent(CONTENT_PATH)
        self.repo = ArtCultureRepository(self.db)
        self.question_ids = self.content.question_ids("M01", "adult")
        self.session = await self.repo.start(
            user_id=88,
            module_id="M01",
            age_mode="adult",
            language="ru",
            question_ids=self.question_ids,
        )

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_session_resumes_and_rejects_stale_answers(self) -> None:
        resumed = await self.repo.start(
            user_id=88,
            module_id="M01",
            age_mode="adult",
            language="en",
            question_ids=self.question_ids,
        )
        self.assertEqual(resumed["id"], self.session["id"])
        question_id = self.question_ids[0]
        question = self.content.question(question_id)
        correct = next(option for option in question["options"] if option["is_correct"])
        result = await self.repo.answer(
            user_id=88,
            session_id=self.session["id"],
            question_id=question_id,
            option_id=correct["id"],
            level=question["level"],
            is_correct=True,
            points=int(question["points"]),
        )
        self.assertTrue(result.is_correct)
        with self.assertRaises(ArtCultureStaleAnswerError):
            await self.repo.answer(
                user_id=88,
                session_id=self.session["id"],
                question_id=question_id,
                option_id=correct["id"],
                level=question["level"],
                is_correct=True,
                points=int(question["points"]),
            )

    async def test_completed_session_produces_mastery_diagnostic(self) -> None:
        for question_id in self.question_ids:
            question = self.content.question(question_id)
            correct = next(option for option in question["options"] if option["is_correct"])
            await self.repo.answer(
                user_id=88,
                session_id=self.session["id"],
                question_id=question_id,
                option_id=correct["id"],
                level=question["level"],
                is_correct=True,
                points=int(question["points"]),
            )
        completed = await self.repo.get_session(user_id=88, session_id=self.session["id"])
        assert completed is not None
        summary = self.repo.summary(
            {**completed, "question_ids_json": json.dumps(completed["question_ids"])},
            self.content.mastery_for("adult"),
        )
        self.assertTrue(summary["mastered"])
        self.assertEqual(summary["overall_percent"], 100)
        self.assertEqual(summary["analysis_percent"], 100)


if __name__ == "__main__":
    unittest.main()
