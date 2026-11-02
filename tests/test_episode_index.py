from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.config import SKIPDB
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.episode_index import rebuild_episode_ids


class EpisodeIndexTests(unittest.TestCase):
    def test_preserves_provider_specific_episode_numbers_and_scope(self) -> None:
        payload = {
            "imdb_show:tt1:s1": {
                "mal:10": {"1": "1"},
                "anilist:20": {"1": "1"},
                "anidb:30:S": {"1": "5"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with DatabaseWriter(root / "runtime.db", root / "evidence.db") as writer:
                source = writer.source_id(SKIPDB)
                title = writer.get_or_create_title(
                    {"mal": "10", "anilist": "20", "anidb": "30"}
                )
                episode = writer.get_or_create_episode(
                    title, episode_key="ep:1", episode_number=1
                )
                writer.add_episode_ref(
                    source,
                    source_title_key="tt1:s1",
                    source_episode_key="e1",
                    episode_id=episode,
                    source_episode_number_text="1",
                )
                stats = rebuild_episode_ids(writer.conn, AniBridgeIndex(payload))
                rows = writer.conn.execute(
                    """
                    SELECT provider, title_external_id, scope, episode_number_text
                    FROM episode_ids ORDER BY provider
                    """
                ).fetchall()

            self.assertEqual(stats.provider_episode_ids, 3)
            self.assertEqual(
                rows,
                [
                    ("anidb", "30", "S", "5"),
                    ("anilist", "20", "", "1"),
                    ("mal", "10", "", "1"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
