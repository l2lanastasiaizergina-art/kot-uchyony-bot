from __future__ import annotations

import unittest

from ortho_game_bot.utils.rate_limit import SlidingWindowLimiter


class RateLimitTests(unittest.TestCase):
    def test_sliding_window(self) -> None:
        limiter = SlidingWindowLimiter(limit=2, window_seconds=1.0)
        self.assertTrue(limiter.allow(7, now=10.0))
        self.assertTrue(limiter.allow(7, now=10.2))
        self.assertFalse(limiter.allow(7, now=10.9))
        self.assertTrue(limiter.allow(7, now=11.01))
        self.assertTrue(limiter.allow(8, now=10.9))


if __name__ == "__main__":
    unittest.main()
