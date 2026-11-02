from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _mapping_fixture import create_mapping_db
from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.config import SKIPDB
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.episode_index import rebuild_episode_ids
from anime_timestamp_db.mapping_identity import MappingAnchorIndex
from anime_timestamp_db.skipdb_mapping import SkipDBMappingIndex


class EpisodeIndexTests(unittest.TestCase):
    def test_preserves_provider_specific_episode_numbers_and_scope(self) -> None:
        payload = {
            "tvdb_show:100:s1": {
                "mal:10": {"1": "1"},
                "anilist:20": {"1": "1"},
                "anidb:30:S": {"1": "5"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mapping_db = root / "mappings.db"
            create_mapping_db(
                mapping_db,
                nodes=[
                    (1, "imdb", "tt1"),
                    (2, "tvdb", "100"),
                    (3, "mal", "10"),
                    (4, "anilist", "20"),
                    (5, "anidb", "30"),
                ],
                edges=[(1, 2)],
                anchors={7001: [1, 2, 3, 4, 5]},
            )
            with DatabaseWriter(root / "runtime.db", root / "evidence.db") as writer:
                source = writer.source_id(SKIPDB)
                anchor = writer.get_or_create_title(7001)
                episode = writer.get_or_create_episode(
                    anchor, episode_key="ep:1", episode_number=1
                )
                writer.add_episode_ref(
                    source,
                    source_title_key="tt1:s1",
                    source_episode_key="e1",
                    episode_id=episode,
                    source_episode_number_text="1",
                )
                with (
                    SkipDBMappingIndex(mapping_db, AniBridgeIndex(payload)) as mappings,
                    MappingAnchorIndex(mapping_db) as identities,
                ):
                    stats = rebuild_episode_ids(writer.conn, mappings, identities)
                rows = writer.conn.execute(
                    """
                    SELECT provider, anchor_id, scope, episode_number_text
                    FROM episode_ids ORDER BY provider
                    """
                ).fetchall()

            self.assertEqual(stats.provider_episode_ids, 3)
            self.assertEqual(
                rows,
                [
                    ("anidb", 7001, "S", "5"),
                    ("anilist", 7001, "", "1"),
                    ("mal", 7001, "", "1"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
