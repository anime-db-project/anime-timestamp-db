from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import zstandard as zstd

from anime_timestamp_db.config import ANIME_MAPPING_DB
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.download import DownloadedSource
from anime_timestamp_db.mapping_enrichment import (
    decompress_mapping_database,
    enrich_titles_from_mapping_db,
    mapping_database_metadata,
)


def _create_mapping_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
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
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (
                ("schema_version", "3"),
                ("database_role", "runtime"),
                ("built_at", "2026-11-02T00:00:00+00:00"),
                ("accepted_edges", "3"),
            ),
        )
        conn.executemany(
            "INSERT INTO nodes(id, provider, external_id) VALUES (?, ?, ?)",
            (
                (1, "mal", "1"),
                (2, "anilist", "101"),
                (3, "kitsu", "201"),
                (4, "anidb", "301"),
            ),
        )
        conn.executemany(
            """
            INSERT INTO edges(
                a_node, b_node, confidence, status,
                evidence_count, evidence_group_count, max_weight
            ) VALUES (?, ?, 100, 'accepted', 2, 2, 100)
            """,
            ((1, 2), (1, 3), (1, 4)),
        )
        conn.execute(
            """
            INSERT INTO conflicts(
                source_node, target_provider, candidate_ids_json, reason
            ) VALUES (1, 'anidb', '["301","302"]', 'multiple accepted target IDs')
            """
        )
        conn.commit()
    finally:
        conn.close()


class MappingEnrichmentTests(unittest.TestCase):
    def test_decompresses_and_adds_only_safe_direct_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_mapping = root / "mappings.db"
            compressed = root / "mappings.db.zst"
            unpacked = root / "unpacked.db"
            _create_mapping_database(raw_mapping)

            compressor = zstd.ZstdCompressor(level=1)
            with raw_mapping.open("rb") as src, compressed.open("wb") as dst:
                compressor.copy_stream(src, dst)

            self.assertEqual(
                decompress_mapping_database(compressed, unpacked),
                unpacked,
            )
            metadata = mapping_database_metadata(unpacked)
            self.assertEqual(metadata["schema_version"], "3")
            self.assertEqual(metadata["accepted_edges"], "3")

            with DatabaseWriter(root / "runtime.db", root / "evidence.db") as writer:
                title = writer.get_or_create_title({"mal": "1"})
                other_title = writer.get_or_create_title(
                    {"mal": "2", "kitsu": "201"}
                )
                self.assertNotEqual(title, other_title)

                download = DownloadedSource(
                    key=ANIME_MAPPING_DB.key,
                    path=compressed,
                    source_url=ANIME_MAPPING_DB.url,
                    final_url=ANIME_MAPPING_DB.url,
                    sha256="abc",
                    size_bytes=compressed.stat().st_size,
                    retrieved_at="2026-11-02T00:00:00+00:00",
                    etag="",
                    last_modified="",
                    from_cache=False,
                )
                snapshot = writer.add_snapshot(
                    ANIME_MAPPING_DB,
                    download,
                    upstream_version=metadata["built_at"],
                )
                stats = enrich_titles_from_mapping_db(
                    unpacked,
                    writer=writer,
                    snapshot_id=snapshot,
                )

                aliases = writer.conn.execute(
                    """
                    SELECT provider, external_id
                    FROM title_ids
                    WHERE title_id=?
                    ORDER BY provider, external_id
                    """,
                    (title,),
                ).fetchall()
                evidence = writer.evidence.execute(
                    """
                    SELECT normalization_status, normalized_provider, normalized_id
                    FROM records
                    WHERE snapshot_id=?
                    """,
                    (snapshot,),
                ).fetchall()

            self.assertEqual(stats.local_mal_titles, 2)
            self.assertEqual(stats.matched_mal_titles, 1)
            self.assertEqual(stats.enriched_titles, 1)
            self.assertEqual(stats.aliases_added, 1)
            self.assertEqual(stats.local_conflicts, 1)
            self.assertEqual(stats.mapping_conflicts, 1)
            self.assertEqual(stats.providers_added, {"anilist": 1})
            self.assertEqual(aliases, [("anilist", "101"), ("mal", "1")])
            self.assertEqual(evidence, [("mapped", "mal", "1")])


if __name__ == "__main__":
    unittest.main()
