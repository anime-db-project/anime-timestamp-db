from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.config import SKIPDB
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.episode_index import rebuild_episode_ids
from anime_timestamp_db.skipdb_mapping import SkipDBMappingIndex


def _mapping_db(path: Path) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                UNIQUE(provider, external_id)
            );
            CREATE TABLE edges (
                a_node INTEGER NOT NULL,
                b_node INTEGER NOT NULL,
                confidence INTEGER NOT NULL,
                status TEXT NOT NULL,
                evidence_count INTEGER NOT NULL,
                evidence_group_count INTEGER NOT NULL,
                max_weight INTEGER NOT NULL,
                PRIMARY KEY(a_node, b_node)
            ) WITHOUT ROWID;
            CREATE TABLE conflicts (
                source_node INTEGER NOT NULL,
                target_provider TEXT NOT NULL,
                candidate_ids_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                PRIMARY KEY(source_node, target_provider)
            ) WITHOUT ROWID;
            """
        )
        conn.executemany(
            "INSERT INTO nodes(id, provider, external_id) VALUES (?, ?, ?)",
            [(1, "imdb", "tt1"), (2, "tvdb", "100")],
        )
        conn.execute(
            """
            INSERT INTO edges(
                a_node, b_node, confidence, status,
                evidence_count, evidence_group_count, max_weight
            ) VALUES (1, 2, 100, 'accepted', 1, 1, 100)
            """
        )
        conn.commit()


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
            _mapping_db(mapping_db)
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
                with SkipDBMappingIndex(
                    mapping_db, AniBridgeIndex(payload)
                ) as mappings:
                    stats = rebuild_episode_ids(writer.conn, mappings)
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
