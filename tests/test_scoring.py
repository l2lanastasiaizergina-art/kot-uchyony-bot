import unittest

from ortho_game_bot.game.scoring import calculate_answer_score


class ScoringTests(unittest.TestCase):
    def test_regular_correct_answer(self) -> None:
        result = calculate_answer_score(is_correct=True, streak_before=0)
        self.assertEqual(result.points, 10)
        self.assertEqual(result.streak_after, 1)

    def test_third_answer_gets_bonus(self) -> None:
        result = calculate_answer_score(is_correct=True, streak_before=2)
        self.assertEqual(result.points, 12)
        self.assertEqual(result.bonus, 2)

    def test_wrong_answer_resets_streak(self) -> None:
        result = calculate_answer_score(is_correct=False, streak_before=9)
        self.assertEqual(result.points, -2)
        self.assertEqual(result.streak_after, 0)


if __name__ == "__main__":
    unittest.main()

