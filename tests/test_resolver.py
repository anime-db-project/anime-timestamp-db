from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anime_timestamp_db.config import BAHA, SKIPDB
from anime_timestamp_db.consensus import rebuild_consensus
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.resolver import TimestampResolver


class ResolverTests(unittest.TestCase):
    def test_normalized_consensus_and_source_only_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = root / "runtime.db"
            evidence = root / "evidence.db"
            with DatabaseWriter(runtime, evidence) as writer:
                skip = writer.source_id(SKIPDB)
                skip_lineage = writer.lineage_id("skipdb", "SkipDB")
                baha = writer.source_id(BAHA)
                baha_lineage = writer.lineage_id("baha", "Baha")
                title = writer.get_or_create_title({"mal": "1", "anilist": "2"})
                episode = writer.get_or_create_episode(
                    title, episode_key="ep:1", episode_number=1
                )
                writer.conn.executemany(
                    """
                    INSERT INTO episode_ids(
                        provider, title_external_id, scope, episode_number_text, episode_id
                    ) VALUES (?, ?, '', ?, ?)
                    """,
                    (("mal", "1", "1", episode), ("anilist", "2", "1", episode)),
                )
                writer.add_segment(
                    episode_id=episode,
                    source_id=skip,
                    lineage_id=skip_lineage,
                    source_segment_id="s1",
                    segment_type="opening",
                    start_ms=10000,
                    end_ms=100000,
                    media_duration_ms=1440000,
                    votes_up=3,
                )
                writer.add_source_segment(
                    source_id=baha,
                    lineage_id=baha_lineage,
                    source_title_key="",
                    source_episode_key="999",
                    source_segment_id="b1",
                    segment_type="opening",
                    start_ms=9000,
                    end_ms=99000,
                )
                rebuild_consensus(writer.conn)
            resolver = TimestampResolver(runtime)
            self.assertEqual(resolver.episode_key("mal", "1", 1), "ep:1")
            self.assertEqual(resolver.title_ids("mal", "1")["anilist"], ["2"])
            self.assertEqual(resolver.get_segments("mal", "1", "ep:1")[0].source, "skipdb")
            self.assertEqual(resolver.get_consensus("mal", "1", "ep:1")[0].member_count, 1)
            self.assertEqual(resolver.get_source_segments("baha", "999")[0].start_ms, 9000)


if __name__ == "__main__":
    unittest.main()
