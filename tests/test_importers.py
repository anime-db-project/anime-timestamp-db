from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.aniskip_importer import import_aniskip
from anime_timestamp_db.config import ANISKIP, BAHA, SKIPDB
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.importers import import_baha, import_skipdb
from anime_timestamp_db.skipdb_mapping import SkipDBMappingIndex


class _Download:
    source_url = "https://example.invalid/source"
    final_url = source_url
    sha256 = "a" * 64
    size_bytes = 1
    retrieved_at = "2026-11-02T00:00:00+00:00"
    etag = ""
    last_modified = ""


def _create_mapping_db(path: Path) -> None:
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
        nodes = [
            (1, "imdb", "tt100"),
            (2, "tvdb", "999"),
            (3, "tmdb_tv", "888"),
            (4, "mal", "10"),
        ]
        conn.executemany(
            "INSERT INTO nodes(id, provider, external_id) VALUES (?, ?, ?)", nodes
        )
        for a, b in ((1, 2), (1, 3), (1, 4)):
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


class ImporterTests(unittest.TestCase):
    def test_aniskip_import_is_mal_native_and_drops_user_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dump = root / "aniskip.csv"
            with dump.open("w", encoding="utf-8", newline="") as handle:
                writer_csv = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "id",
                        "created_at",
                        "updated_at",
                        "episode_length",
                        "skip_type",
                        "skip_time_start",
                        "skip_time_end",
                        "mal_id",
                        "episode_number",
                        "user_id",
                        "external_id",
                    ],
                )
                writer_csv.writeheader()
                writer_csv.writerow(
                    {
                        "id": "1",
                        "created_at": "2020-01-01",
                        "updated_at": "2026-01-01",
                        "episode_length": "1420",
                        "skip_type": "op",
                        "skip_time_start": "40.0",
                        "skip_time_end": "130.0",
                        "mal_id": "570",
                        "episode_number": "1",
                        "user_id": "private-user-id",
                        "external_id": "uuid-1",
                    }
                )

            runtime = root / "timestamps.db"
            evidence = root / "evidence.db"
            with DatabaseWriter(runtime, evidence) as writer:
                snapshot = writer.add_snapshot(ANISKIP, _Download())
                stats = import_aniskip(dump, writer=writer, snapshot_id=snapshot)

            self.assertEqual(stats.records, 1)
            self.assertEqual(stats.runtime_segments, 1)
            with closing(sqlite3.connect(runtime)) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT provider, external_id FROM title_ids"
                    ).fetchone(),
                    ("mal", "570"),
                )
                self.assertEqual(
                    conn.execute(
                        """
                        SELECT provider, title_external_id, episode_number_text
                        FROM episode_ids
                        """
                    ).fetchone(),
                    ("mal", "570", "1"),
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT segment_type, start_ms, end_ms, media_duration_ms FROM segments"
                    ).fetchone(),
                    ("opening", 40000, 130000, 1420000),
                )
            with closing(sqlite3.connect(evidence)) as conn:
                evidence_text = " ".join(
                    str(value)
                    for row in conn.execute(
                        "SELECT payload_sha256, metadata_json FROM records"
                    )
                    for value in row
                )
                self.assertNotIn("private-user-id", evidence_text)

    def test_skipdb_import_keeps_evidence_but_runtime_only_approved_mapped(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dump = root / "skipdb.json"
            dump.write_text(
                json.dumps(
                    {
                        "segments": [
                            {
                                "imdb_id": "tt100",
                                "title": "Example",
                                "media_type": "series",
                                "season": 1,
                                "episode": 2,
                                "segment_type": "intro",
                                "status": "approved",
                                "submitted_by": "private-user-id",
                                "start_ms": 1000,
                                "end_ms": 91000,
                                "duration_ms": 1440000,
                                "votes_up": 5,
                                "votes_down": 1,
                                "score": 4,
                                "created_at": "2026-01-01",
                            },
                            {
                                "imdb_id": "tt100",
                                "title": "Example",
                                "media_type": "series",
                                "season": 1,
                                "episode": 2,
                                "segment_type": "outro",
                                "status": "pending",
                                "submitted_by": "private-user-id-2",
                                "start_ms": 1300000,
                                "end_ms": 1390000,
                                "duration_ms": 1440000,
                                "votes_up": 1,
                                "votes_down": 0,
                                "score": 1,
                                "created_at": "2026-01-02",
                            },
                        ]
                    }
                ),
                "utf-8",
            )
            bridge = AniBridgeIndex(
                {
                    "tvdb_show:999:s1": {
                        "mal:10": {"1-12": "1-12"},
                        "anilist:20": {"1-12": "1-12"},
                    },
                    "tmdb_show:888:s1": {
                        "mal:10": {"1-12": "1-12"},
                        "anilist:20": {"1-12": "1-12"},
                    },
                }
            )
            mapping_db = root / "mappings.db"
            _create_mapping_db(mapping_db)
            runtime = root / "timestamps.db"
            evidence = root / "evidence.db"
            with SkipDBMappingIndex(mapping_db, bridge) as mappings:
                with DatabaseWriter(runtime, evidence) as writer:
                    snapshot = writer.add_snapshot(SKIPDB, _Download())
                    stats = import_skipdb(
                        dump,
                        writer=writer,
                        snapshot_id=snapshot,
                        mappings=mappings,
                    )
            self.assertEqual(stats.records, 2)
            self.assertEqual(stats.runtime_segments, 1)
            with closing(sqlite3.connect(runtime)) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0], 1
                )
                self.assertEqual(
                    conn.execute("SELECT episode_key FROM episodes").fetchone()[0],
                    "ep:2",
                )
                ids = dict(conn.execute("SELECT provider, external_id FROM title_ids"))
                self.assertEqual(ids, {"mal": "10"})
                self.assertEqual(
                    conn.execute(
                        "SELECT mapping_method, mapping_confidence FROM segments"
                    ).fetchone(),
                    ("exact-dual-bridge", 1.0),
                )
            with closing(sqlite3.connect(evidence)) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 2
                )
                metadata = " ".join(
                    row[0] for row in conn.execute("SELECT metadata_json FROM records")
                )
                self.assertNotIn("private-user-id", metadata)

    def test_baha_is_source_addressable_without_fake_title_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dump = root / "baha.json"
            dump.write_text(json.dumps({"123": {"OP": [10.5, 89.5]}}), "utf-8")
            runtime = root / "timestamps.db"
            evidence = root / "evidence.db"
            with DatabaseWriter(runtime, evidence) as writer:
                snapshot = writer.add_snapshot(BAHA, _Download())
                stats = import_baha(dump, writer=writer, snapshot_id=snapshot)
            self.assertEqual(stats.source_only_segments, 1)
            with closing(sqlite3.connect(runtime)) as conn:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM titles").fetchone()[0], 0
                )
                row = conn.execute(
                    """
                    SELECT source_episode_key, segment_type, start_ms, end_ms
                    FROM source_segments
                    """
                ).fetchone()
                self.assertEqual(row, ("123", "opening", 10500, 100000))


if __name__ == "__main__":
    unittest.main()
