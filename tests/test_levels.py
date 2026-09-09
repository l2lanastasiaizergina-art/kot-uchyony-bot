from __future__ import annotations

import unittest

from ortho_game_bot.game.levels import ORTHOGRAPHY_LEVELS, level_for_grade


class OrthographyLevelTests(unittest.TestCase):
    def test_levels_cover_the_school_program(self) -> None:
        self.assertEqual([level.code for level in ORTHOGRAPHY_LEVELS], ["A0", "A1", "A2", "B1", "B2", "C1"])
        self.assertEqual(level_for_grade(1).code, "A0")
        self.assertEqual(level_for_grade(2).code, "A1")
        self.assertEqual(level_for_grade(6).code, "B1")
        self.assertEqual(level_for_grade(11).code, "C1")

    def test_zero_level_uses_only_simplest_first_pack(self) -> None:
        level = ORTHOGRAPHY_LEVELS[0]
        self.assertEqual((level.min_grade, level.max_grade, level.max_difficulty), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
