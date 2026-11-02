from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.database import create_runtime_database
from anime_timestamp_db.resolver import TimestampResolver


class ResolverTests(unittest.TestCase):
    def _build_sample(self, path: Path) -> None:
        create_runtime_database(path)
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            source_id = conn.execute(
                """
                INSERT INTO sources(source_key, display_name)
                VALUES('open-anime-timestamps', 'Open Anime Timestamps')
                """
            ).lastrowid
            lineage_id = conn.execute(
                "INSERT INTO lineages(lineage_key, display_name) VALUES('aniskip', 'AniSkip')"
            ).lastrowid
            title_id = conn.execute(
                "INSERT INTO titles(canonical_provider, canonical_id) VALUES('mal', '1')"
            ).lastrowid
            conn.executemany(
                "INSERT INTO title_ids(provider, external_id, title_id) VALUES(?, ?, ?)",
                (
                    ("mal", "1", title_id),
                    ("anilist", "1", title_id),
                    ("anidb", "23", title_id),
                ),
            )
            episode_id = conn.execute(
                """
                INSERT INTO episodes(
                    title_id, episode_key, episode_number_text, episode_number
                ) VALUES(?, 'ep:1', '1', 1)
                """,
                (title_id,),
            ).lastrowid
            conn.execute(
                """
                INSERT INTO segments(
                    episode_id, source_id, lineage_id, source_segment_id,
                    segment_type, start_ms, end_ms, confidence
                ) VALUES(?, ?, ?, 'op', 'opening', 90000, 180000, 0.95)
                """,
                (episode_id, source_id, lineage_id),
            )
            consensus_id = conn.execute(
                """
                INSERT INTO consensus_segments(
                    episode_id, segment_type, cluster_index,
                    start_ms, end_ms, member_count, lineage_count,
                    algorithm, tolerance_ms
                ) VALUES(?, 'opening', 0, 90000, 180000, 1, 1, 'median', 5000)
                """,
                (episode_id,),
            ).lastrowid
            segment_id = conn.execute("SELECT id FROM segments").fetchone()[0]
            conn.execute(
                "INSERT INTO consensus_members(consensus_id, segment_id) VALUES(?, ?)",
                (consensus_id, segment_id),
            )
            conn.commit()

    def test_resolves_source_and_original_lineage_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps.db"
            self._build_sample(path)
            resolver = TimestampResolver(path)

            segments = resolver.get_segments("mal", "1", "ep:1")
            self.assertEqual(len(segments), 1)
            self.assertEqual(segments[0].source, "open-anime-timestamps")
            self.assertEqual(segments[0].lineage, "aniskip")
            self.assertEqual(segments[0].segment_type, "opening")

    def test_title_identity_can_be_queried_from_any_known_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps.db"
            self._build_sample(path)
            resolver = TimestampResolver(path)

            ids = resolver.title_ids("anidb", "23")
            self.assertEqual(ids["mal"], ["1"])
            self.assertEqual(ids["anilist"], ["1"])

    def test_consensus_is_separate_from_source_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps.db"
            self._build_sample(path)
            resolver = TimestampResolver(path)

            consensus = resolver.get_consensus("mal", "1", "ep:1")
            self.assertEqual(len(consensus), 1)
            self.assertEqual(consensus[0].lineage_count, 1)
            self.assertEqual(consensus[0].tolerance_ms, 5000)


if __name__ == "__main__":
    unittest.main()
