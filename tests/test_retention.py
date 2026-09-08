import unittest

from ortho_game_bot.game.retention import (
    calculate_daily_reward,
    daily_multiplier_percent,
    league_for_score,
    qualifies_for_daily_streak,
)


class RetentionTests(unittest.TestCase):
    def test_multiplier_reaches_double_on_day_seven(self) -> None:
        self.assertEqual(daily_multiplier_percent(1), 100)
        self.assertEqual(daily_multiplier_percent(3), 125)
        self.assertEqual(daily_multiplier_percent(7), 200)

    def test_multiplier_is_limited_to_three_rounds(self) -> None:
        boosted = calculate_daily_reward(raw_points=100, streak_days=7, boosted_rounds_used=2)
        regular = calculate_daily_reward(raw_points=100, streak_days=7, boosted_rounds_used=3)
        self.assertEqual(boosted.awarded_points, 200)
        self.assertEqual(regular.awarded_points, 100)

    def test_penalty_is_not_doubled(self) -> None:
        reward = calculate_daily_reward(raw_points=-2, streak_days=20, boosted_rounds_used=0)
        self.assertEqual(reward.awarded_points, -2)

    def test_streak_requires_completed_round(self) -> None:
        self.assertFalse(qualifies_for_daily_streak(answers_attempted=9))
        self.assertTrue(qualifies_for_daily_streak(answers_attempted=10))

    def test_league_progression(self) -> None:
        self.assertEqual(league_for_score(0).title, "Котёнок")
        self.assertEqual(league_for_score(3_500).title, "Профессор")
        self.assertEqual(league_for_score(20_000).title, "Легенда")


if __name__ == "__main__":
    unittest.main()

