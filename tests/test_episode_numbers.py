from __future__ import annotations

import unittest

from anime_timestamp_db.episode_numbers import normalize_episode_number


class EpisodeNumberTests(unittest.TestCase):
    def test_preserves_fractional_numbers(self) -> None:
        self.assertEqual(normalize_episode_number(12.5), "12.5")
        self.assertEqual(normalize_episode_number("12.5"), "12.5")
        self.assertEqual(normalize_episode_number(12.0), "12")
        self.assertEqual(normalize_episode_number("12.0"), "12")

    def test_rejects_non_numeric_values(self) -> None:
        with self.assertRaises(ValueError):
            normalize_episode_number("")
        with self.assertRaises(ValueError):
            normalize_episode_number("special")


if __name__ == "__main__":
    unittest.main()
