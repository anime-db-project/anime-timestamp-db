from __future__ import annotations

import unittest

from anime_timestamp_db.anibridge import AniBridgeIndex, parse_descriptor, parse_range


class AniBridgeTests(unittest.TestCase):
    def test_parsers(self) -> None:
        self.assertEqual(parse_descriptor("anidb:23:R").provider, "anidb")
        self.assertEqual(parse_range("3").start, 3)
        self.assertEqual(parse_range("3").end, 3)
        self.assertIsNone(parse_range("3-").end)
        self.assertIsNone(parse_range("5-2"))

    def test_series_mapping_accepts_safe_one_to_one_ranges(self) -> None:
        index = AniBridgeIndex(
            {
                "imdb_show:tt1:s2": {
                    "mal:100": {"1-4": "5-8"},
                    "anilist:200": {"1-4": "5-8"},
                    "anidb:300:R": {"1-4": "5-8"},
                }
            }
        )
        result = index.resolve_series_episode("tt1", 2, 3)
        self.assertEqual(result.skipped_complex_targets, 0)
        self.assertEqual(
            {(x.descriptor.provider, x.descriptor.external_id, x.episode_number) for x in result.targets},
            {("mal", "100", 7), ("anilist", "200", 7), ("anidb", "300", 7)},
        )

    def test_ratio_mapping_is_not_projected(self) -> None:
        index = AniBridgeIndex(
            {"imdb_show:tt1:s1": {"mal:100": {"1-12": "1-24|2"}}}
        )
        result = index.resolve_series_episode("tt1", 1, 2)
        self.assertEqual(result.targets, ())
        self.assertEqual(result.skipped_complex_targets, 1)

    def test_multi_target_ranges_are_offset_mapped(self) -> None:
        index = AniBridgeIndex(
            {"imdb_show:tt1:s1": {"mal:100": {"1-4": "1-2,4-5"}}}
        )
        self.assertEqual(
            index.resolve_series_episode("tt1", 1, 3).targets[0].episode_number,
            4,
        )


if __name__ == "__main__":
    unittest.main()
