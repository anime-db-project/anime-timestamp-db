from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.config import SKIPDB
from anime_timestamp_db.consensus import rebuild_consensus
from anime_timestamp_db.database import DatabaseWriter


class ConsensusTests(unittest.TestCase):
    def test_clusters_nearby_ranges_and_separates_different_media_durations(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime.db"
            evidence = root / "evidence.db"
            with DatabaseWriter(runtime, evidence) as writer:
                source = writer.source_id(SKIPDB)
                lineage = writer.lineage_id("skipdb", "SkipDB")
                title = writer.get_or_create_title({"mal": "1"})
                episode = writer.get_or_create_episode(
                    title, episode_key="ep:1", episode_number=1
                )
                for segment_id, start, end, duration, score in (
                    ("a", 10000, 100000, 1440000, 5),
                    ("b", 11000, 101000, 1441000, 3),
                    ("c", 20000, 110000, 1500000, 5),
                ):
                    writer.add_segment(
                        episode_id=episode,
                        source_id=source,
                        lineage_id=lineage,
                        source_segment_id=segment_id,
                        segment_type="opening",
                        start_ms=start,
                        end_ms=end,
                        media_duration_ms=duration,
                        quality_score=score,
                        votes_up=3,
                    )
                result = rebuild_consensus(writer.conn)
                self.assertEqual(result["consensus_segments"], 2)
            with closing(sqlite3.connect(runtime)) as conn:
                rows = conn.execute(
                    "SELECT member_count, start_ms, end_ms FROM consensus_segments ORDER BY cluster_index"
                ).fetchall()
                self.assertEqual(rows[0][0], 2)
                self.assertIn(rows[0][1], {10000, 11000})
                self.assertEqual(rows[1][0], 1)


if __name__ == "__main__":
    unittest.main()
