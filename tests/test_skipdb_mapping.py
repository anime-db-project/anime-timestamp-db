from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.anibridge import AniBridgeIndex
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
            CREATE INDEX edges_b_accepted_idx
                ON edges(b_node, a_node)
                WHERE status='accepted';
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
            [
                (1, "imdb", "tt1"),
                (2, "tvdb", "100"),
                (3, "tmdb_tv", "200"),
                (4, "mal", "10"),
                (5, "mal", "11"),
            ],
        )
        for a, b in ((1, 2), (1, 3), (1, 4), (1, 5)):
            conn.execute(
                """
                INSERT INTO edges(
                    a_node, b_node, confidence, status,
                    evidence_count, evidence_group_count, max_weight
                ) VALUES (?, ?, 100, 'accepted', 1, 1, 100)
                """,
                (min(a, b), max(a, b)),
            )
        conn.commit()


class SkipDBMappingTests(unittest.TestCase):
    def test_tvdb_tmdb_bridge_and_season_offset_inference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.db"
            _mapping_db(path)
            bridge = AniBridgeIndex(
                {
                    "tvdb_show:100:s1": {
                        "mal:10": {"1": "1", "3": "3"},
                    },
                    "tmdb_show:200:s1": {
                        "mal:10": {"1": "1", "3": "3"},
                    },
                }
            )
            rows = [
                {
                    "imdb_id": "tt1",
                    "media_type": "series",
                    "season": 1,
                    "episode": episode,
                }
                for episode in (1, 2, 3)
            ]
            with SkipDBMappingIndex(path, bridge) as index:
                candidates = index.title_candidates("tt1")
                self.assertEqual(candidates.mal, ("10", "11"))
                plan, stats = index.prepare_series_episode_map(rows)

            self.assertEqual(stats.exact_episodes, 2)
            self.assertEqual(stats.inferred_episodes, 1)
            self.assertEqual(plan[("tt1", 1, 1)].method, "exact-dual-bridge")
            inferred = plan[("tt1", 1, 2)]
            self.assertEqual(inferred.method, "inferred-season-offset")
            self.assertEqual(inferred.ids, {"mal": "10"})
            self.assertEqual(inferred.episode_number, 2)
            self.assertEqual(
                inferred.mapping_confidence
                if hasattr(inferred, "mapping_confidence")
                else inferred.confidence,
                0.85,
            )

    def test_compact_edge_lookup_uses_primary_and_reverse_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.db"
            _mapping_db(path)
            bridge = AniBridgeIndex({})
            with SkipDBMappingIndex(path, bridge) as index:
                node_id = index._imdb_node("tt1")
                assert node_id is not None
                plan = index.conn.execute(
                    """
                    EXPLAIN QUERY PLAN
                    WITH direct_targets(target_node) AS (
                        SELECT b_node FROM edges
                        WHERE a_node=? AND status='accepted'
                        UNION ALL
                        SELECT a_node FROM edges
                        WHERE b_node=? AND status='accepted'
                    )
                    SELECT target.external_id
                    FROM direct_targets AS direct
                    JOIN nodes AS target ON target.id=direct.target_node
                    WHERE target.provider=?
                    ORDER BY target.external_id
                    """,
                    (node_id, node_id, "tvdb"),
                ).fetchall()
            details = " ".join(str(row[3]) for row in plan)
            self.assertIn("PRIMARY KEY", details)
            self.assertNotIn("SCAN edges", details)

    def test_conflicted_bridge_route_is_not_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.db"
            _mapping_db(path)
            with closing(sqlite3.connect(path)) as conn:
                conn.execute(
                    """
                    INSERT INTO conflicts(source_node, target_provider, candidate_ids_json, reason)
                    VALUES (1, 'tvdb', '["100","101"]', 'ambiguous')
                    """
                )
                conn.commit()
            bridge = AniBridgeIndex(
                {
                    "tvdb_show:100:s1": {"mal:10": {"1": "1"}},
                    "tmdb_show:200:s1": {"mal:10": {"1": "1"}},
                }
            )
            with SkipDBMappingIndex(path, bridge) as index:
                resolved = index.resolve_exact_series_episode("tt1", 1, 1)
            self.assertIsNotNone(resolved)
            assert resolved is not None
            self.assertEqual(resolved.method, "exact-single-bridge")
            self.assertEqual(resolved.confidence, 0.98)
            self.assertEqual(resolved.routes, ("tmdb_show:200:s1",))


if __name__ == "__main__":
    unittest.main()
