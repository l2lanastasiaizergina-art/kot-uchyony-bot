from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ortho_game_bot.ai_course import AICourseContent, AICourseRepository, AICourseStaleAnswerError
from ortho_game_bot.database import Database, UserRepository

CONTENT_PATH = Path(__file__).parents[1] / "data" / "ai_course" / "content.ru.json.gz"


class AICourseContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.content = AICourseContent(CONTENT_PATH)

    def test_pack_has_full_competency_diagnostic_and_mission_matrix(self) -> None:
        self.assertEqual(len(self.content.competencies), 8)
        self.assertEqual(len(self.content.age_profiles), 4)
        self.assertEqual(len(self.content.mission_ids()), 20)
        for age_code in ("A1", "A2", "A3", "A4"):
            self.assertEqual(len(self.content.diagnostic_tasks(age_code)), 16)
            for mission_id in self.content.mission_ids():
                public = self.content.public_mission(
                    self.content.mission(mission_id), age_code
                )
                self.assertEqual(len(public["check"]["options"]), 4)
                self.assertNotIn("correct_option", public["check"])

    def test_diagnostic_summary_returns_all_eight_competencies(self) -> None:
        answers = []
        for task in self.content.diagnostic_tasks("A2"):
            answers.append(
                {
                    "competency_id": task["competency_id"],
                    "score": 3,
                }
            )
        summary = self.content.diagnostic_summary(answers)
        self.assertEqual(summary["overall_percent"], 100)
        self.assertEqual(len(summary["competencies"]), 8)
        self.assertIn(summary["recommended_mission_id"], self.content.mission_ids())


class AICourseRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "test.sqlite3")
        await self.db.migrate()
        self.users = UserRepository(self.db)
        await self.users.register_or_update(818, "ai_learner", "Исследователь")
        self.repo = AICourseRepository(self.db)
        self.content = AICourseContent(CONTENT_PATH)
        await self.repo.set_profile(user_id=818, age_code="A3")

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_diagnostic_answers_are_isolated_by_age_profile(self) -> None:
        task = self.content.diagnostic_tasks("A3")[0]
        score = self.content.diagnostic_score("A3", task["task_id"], 1)
        await self.repo.answer_diagnostic(
            user_id=818,
            age_code="A3",
            task_id=task["task_id"],
            competency_id=task["competency_id"],
            selected_option=1,
            score=score,
        )
        self.assertEqual(len(await self.repo.diagnostic_answers(user_id=818, age_code="A3")), 1)
        self.assertEqual(len(await self.repo.diagnostic_answers(user_id=818, age_code="A2")), 0)
        with self.assertRaises(AICourseStaleAnswerError):
            await self.repo.answer_diagnostic(
                user_id=818,
                age_code="A3",
                task_id=task["task_id"],
                competency_id=task["competency_id"],
                selected_option=1,
                score=score,
            )

    async def test_mission_requires_check_then_practical_evidence(self) -> None:
        mission_id = "AI-M01"
        await self.repo.start_mission(user_id=818, mission_id=mission_id)
        check = self.content.mission_variant(mission_id, "A3")["check"]
        wrong = (int(check["correct_option"]) + 1) % 4
        first = await self.repo.answer_mission_check(
            user_id=818,
            mission_id=mission_id,
            selected_option=wrong,
            correct_option=int(check["correct_option"]),
        )
        self.assertTrue(first.allow_retry)
        with self.assertRaises(AICourseStaleAnswerError):
            await self.repo.save_evidence(
                user_id=818, mission_id=mission_id, evidence_text="Практика готова"
            )
        second = await self.repo.answer_mission_check(
            user_id=818,
            mission_id=mission_id,
            selected_option=int(check["correct_option"]),
            correct_option=int(check["correct_option"]),
        )
        self.assertTrue(second.check_completed)
        saved = await self.repo.save_evidence(
            user_id=818,
            mission_id=mission_id,
            evidence_text="Разделил примеры на ИИ и обычную автоматизацию.",
        )
        self.assertEqual(saved["status"], "completed")
        self.assertTrue(saved["evidence_text"])


if __name__ == "__main__":
    unittest.main()
