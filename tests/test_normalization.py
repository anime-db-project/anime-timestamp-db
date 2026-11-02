from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anime_timestamp_db.audit import audit_runtime
from anime_timestamp_db.config import ANISKIP, SKIPDB
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.normalization import merge_movie_episode_aliases


class NormalizationTests(unittest.TestCase):
    def test_merges_movie_alias_into_existing_episode_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with DatabaseWriter(root / "runtime.db", root / "evidence.db") as writer:
                aniskip_source = writer.source_id(ANISKIP)
                skipdb_source = writer.source_id(SKIPDB)
                aniskip_lineage = writer.lineage_id("aniskip", "AniSkip")
                skipdb_lineage = writer.lineage_id("skipdb", "SkipDB")
                title = writer.get_or_create_title(
                    {
                        "mal": "48561",
                        "anilist": "131573",
                        "anidb": "16169",
                        "imdb_movie": "tt14331144",
                    }
                )
                episode_one = writer.get_or_create_episode(
                    title,
                    episode_key="ep:1",
                    episode_number=1,
                )
                movie = writer.get_or_create_episode(
                    title,
                    episode_key="movie",
                    episode_number=1,
                    duration_ms=7200000,
                )
                writer.add_episode_ref(
                    aniskip_source,
                    source_title_key="48561",
                    source_episode_key="1",
                    episode_id=episode_one,
                    source_episode_number_text="1",
                )
                writer.add_episode_ref(
                    skipdb_source,
                    source_title_key="tt14331144",
                    source_episode_key="movie",
                    episode_id=movie,
                    source_episode_number_text="",
                )
                writer.add_segment(
                    episode_id=episode_one,
                    source_id=aniskip_source,
                    lineage_id=aniskip_lineage,
                    source_segment_id="aniskip:one",
                    segment_type="opening",
                    start_ms=0,
                    end_ms=90000,
                )
                writer.add_segment(
                    episode_id=movie,
                    source_id=skipdb_source,
                    lineage_id=skipdb_lineage,
                    source_segment_id="skipdb:movie",
                    segment_type="opening",
                    start_ms=1000,
                    end_ms=91000,
                )
                writer.conn.execute(
                    """
                    INSERT INTO episode_ids(
                        provider, title_external_id, scope,
                        episode_number_text, episode_id
                    ) VALUES ('mal', '48561', '', '1', ?)
                    """,
                    (episode_one,),
                )
                writer.conn.execute(
                    """
                    INSERT INTO episode_ids(
                        provider, title_external_id, scope,
                        episode_number_text, episode_id
                    ) VALUES ('imdb_movie', 'tt14331144', '', '1', ?)
                    """,
                    (movie,),
                )

                stats = merge_movie_episode_aliases(writer.conn)

                episodes = writer.conn.execute(
                    """
                    SELECT id, episode_key, duration_ms
                    FROM episodes
                    WHERE title_id=?
                    ORDER BY id
                    """,
                    (title,),
                ).fetchall()
                segment_episodes = {
                    int(row[0])
                    for row in writer.conn.execute(
                        "SELECT episode_id FROM segments ORDER BY id"
                    )
                }
                reference_episodes = {
                    int(row[0])
                    for row in writer.conn.execute(
                        "SELECT episode_id FROM episode_refs"
                    )
                }
                id_episodes = {
                    int(row[0])
                    for row in writer.conn.execute("SELECT episode_id FROM episode_ids")
                }

            audit = audit_runtime(root / "runtime.db")
            self.assertEqual(audit["duplicate_movie_episode_aliases"], 0)
            self.assertEqual(stats.movie_episode_merges, 1)
            self.assertEqual(stats.segments_repointed, 1)
            self.assertEqual(stats.episode_refs_repointed, 1)
            self.assertEqual(stats.episode_ids_repointed, 1)
            self.assertEqual(stats.durations_filled, 1)
            self.assertEqual(episodes, [(episode_one, "ep:1", 7200000)])
            self.assertEqual(segment_episodes, {episode_one})
            self.assertEqual(reference_episodes, {episode_one})
            self.assertEqual(id_episodes, {episode_one})


if __name__ == "__main__":
    unittest.main()
