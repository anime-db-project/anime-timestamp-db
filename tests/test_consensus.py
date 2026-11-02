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
                anchor = writer.get_or_create_title(101)
                episode = writer.get_or_create_episode(
                    anchor, episode_key="ep:1", episode_number=1
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

    def test_consensus_votes_once_per_lineage_and_ignores_ineligible_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime.db"
            evidence = root / "evidence.db"
            with DatabaseWriter(runtime, evidence) as writer:
                source_a = writer.source_id(SKIPDB)
                from anime_timestamp_db.config import OPEN_ANIME_TIMESTAMPS

                source_b = writer.source_id(OPEN_ANIME_TIMESTAMPS)
                lineage_a = writer.lineage_id("mirror-a", "Mirror A")
                lineage_b = writer.lineage_id("independent-b", "Independent B")
                lineage_c = writer.lineage_id("independent-c", "Independent C")
                aggregate = writer.lineage_id("aggregate", "Aggregate")
                anchor = writer.get_or_create_title(101)
                episode = writer.get_or_create_episode(
                    anchor, episode_key="ep:1", episode_number=1
                )
                for index in range(5):
                    writer.add_segment(
                        episode_id=episode,
                        source_id=source_a if index == 0 else source_b,
                        lineage_id=lineage_a,
                        source_segment_id=f"mirror-{index}",
                        segment_type="opening",
                        start_ms=10000,
                        end_ms=100000,
                    )
                for segment_id, lineage in (("b", lineage_b), ("c", lineage_c)):
                    writer.add_segment(
                        episode_id=episode,
                        source_id=source_b,
                        lineage_id=lineage,
                        source_segment_id=segment_id,
                        segment_type="opening",
                        start_ms=20000,
                        end_ms=110000,
                    )
                writer.add_segment(
                    episode_id=episode,
                    source_id=source_b,
                    lineage_id=aggregate,
                    source_segment_id="excluded",
                    segment_type="opening",
                    start_ms=1000,
                    end_ms=91000,
                    consensus_eligible=False,
                )
                rebuild_consensus(writer.conn)

            with closing(sqlite3.connect(runtime)) as conn:
                row = conn.execute(
                    "SELECT member_count, lineage_count, start_ms FROM consensus_segments"
                ).fetchone()
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row[0], 7)
                self.assertEqual(row[1], 3)
                self.assertEqual(row[2], 20000)
                excluded = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM consensus_members cm
                    JOIN segments s ON s.id=cm.segment_id
                    WHERE s.source_segment_id='excluded'
                    """
                ).fetchone()[0]
                self.assertEqual(excluded, 0)


if __name__ == "__main__":
    unittest.main()
