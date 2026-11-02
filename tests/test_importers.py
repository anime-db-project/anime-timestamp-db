from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.config import ANISKIP, BAHA, SKIPDB
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.importers import import_aniskip, import_baha, import_skipdb


class _Download:
    source_url = "https://example.invalid/source"
    final_url = source_url
    sha256 = "a" * 64
    size_bytes = 1
    retrieved_at = "2026-11-02T00:00:00+00:00"
    etag = ""
    last_modified = ""


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
            mappings = AniBridgeIndex(
                {
                    "imdb_show:tt100:s1": {
                        "mal:10": {"1-12": "1-12"},
                        "anilist:20": {"1-12": "1-12"},
                    }
                }
            )
            runtime = root / "timestamps.db"
            evidence = root / "evidence.db"
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
                self.assertEqual(ids, {"mal": "10", "anilist": "20"})
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
