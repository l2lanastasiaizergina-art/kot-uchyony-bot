from __future__ import annotations

import json
import unittest
from pathlib import Path

from ortho_game_bot.game.distractors import generate_choice_options


class DistractorTests(unittest.TestCase):
    def test_every_content_word_has_four_unique_options(self) -> None:
        words_directory = Path(__file__).parents[1] / "data" / "words"
        checked = 0
        for path in sorted(words_directory.glob("grade_*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for word in payload["words"]:
                options = generate_choice_options(
                    word["answer"],
                    word.get("orthograms", []),
                    seed=word["id"],
                )
                self.assertEqual(len(options), 4)
                self.assertEqual(len({option.casefold() for option in options}), 4)
                self.assertIn(word["answer"], options)
                checked += 1
        self.assertEqual(checked, 1543)


if __name__ == "__main__":
    unittest.main()
