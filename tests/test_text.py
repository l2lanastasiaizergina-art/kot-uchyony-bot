import unittest

from ortho_game_bot.utils.text import answers_equal, normalize_answer


class TextTests(unittest.TestCase):
    def test_normalizes_spaces_case_and_dash(self) -> None:
        self.assertEqual(normalize_answer("  ПОЛ—ЛИМОНА  "), "пол-лимона")

    def test_yo_policy_is_configurable(self) -> None:
        self.assertTrue(answers_equal("береза", "берёза", accept_e_for_yo=True))
        self.assertFalse(answers_equal("береза", "берёза", accept_e_for_yo=False))


if __name__ == "__main__":
    unittest.main()

