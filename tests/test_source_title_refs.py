"""Source-native title identity is not evidence of canonical episode numbering."""

from __future__ import annotations

import gzip
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from anime_timestamp_db.__main__ import main
from anime_timestamp_db.api_importer import import_api_checkpoint
from anime_timestamp_db.audit import audit_runtime
from anime_timestamp_db.config import ANIME_SKIP_API, ANISKIP_API
from anime_timestamp_db.database import (
    DatabaseWriter,
    IdentityConflict,
    inspect_database,
)
from anime_timestamp_db.distribution import compact_runtime_database
from anime_timestamp_db.mapping_identity import MappingAnchorIndex
from anime_timestamp_db.resolver import TimestampResolver
from tests._mapping_fixture import create_mapping_db


class SourceTitleReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.mapping = self.root / "mappings.db"
        create_mapping_db(
            self.mapping,
            nodes=[
                (1, "mal", "10"),
                (2, "anilist", "20"),
                (3, "anilist", "30"),
            ],
            anchors={101: [1, 2], 303: [3]},
        )
        self.download = SimpleNamespace(
            source_url="https://example.invalid",
            final_url="https://example.invalid",
            sha256="a" * 64,
            size_bytes=1,
            retrieved_at="2026-11-04T00:00:00Z",
            etag="",
            last_modified="",
        )
        self.runtime = self.root / "runtime.db"
        self.evidence = self.root / "evidence.db"

    def checkpoint(self, records: dict) -> Path:
        path = self.root / "anime_skip.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump({"version": 1, "source": "anime_skip", "records": records}, f)
        return path

    @staticmethod
    def row(title_id: str, *, episode_proven: bool = False) -> dict:
        return {
            "source": "anime_skip",
            "native_title_id": title_id,
            "episode": 7,
            "type": "opening",
            "start_ms": 12000,
            "end_ms": 87000,
            "duration_ms": 1400000,
            "source_segment_id": "segment-" + title_id,
            "upstream_episode_id": "uuid-" + title_id,
            "episode_identity_proven": episode_proven,
            "upstream_lineage": "ANIME_SKIP",
        }

    def test_all_known_titles_exist_without_fabricating_episodes(self) -> None:
        path = self.checkpoint(
            {
                "20": {"status": "found", "segments": [self.row("20")]},
                "30": {"status": "found", "segments": [self.row("30")]},
            }
        )
        with (
            MappingAnchorIndex(self.mapping) as identities,
            DatabaseWriter(self.runtime, self.evidence) as writer,
        ):
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            stats = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
            )
            self.assertEqual(stats.source_only_segments, 2)
            self.assertEqual(stats.runtime_segments, 0)
            self.assertEqual(
                writer.conn.execute(
                    "SELECT anchor_id FROM titles ORDER BY 1"
                ).fetchall(),
                [(101,), (303,)],
            )
            self.assertEqual(
                writer.conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0], 0
            )
            self.assertEqual(
                writer.conn.execute(
                    "SELECT COUNT(*) FROM source_title_refs"
                ).fetchone()[0],
                2,
            )
        compact = self.root / "compact.db"
        compact_runtime_database(self.runtime, compact)
        resolver = TimestampResolver(compact)
        self.assertEqual(
            [
                (r.source, r.source_title_key)
                for r in resolver.get_source_title_refs_by_anchor(303)
            ],
            [("anime-skip-api", "30")],
        )
        self.assertEqual(
            [
                (r.source_title_key, r.source_episode_key)
                for r in resolver.get_source_segments_by_anchor("amdb:101")
            ],
            [("20", "uuid-20")],
        )
        self.assertEqual(
            resolver.get_source_segments_by_anchor("amdb:101", source="aniskip-api"), []
        )
        self.assertEqual(
            len(
                resolver.get_source_segments_by_anchor(
                    "amdb:101", source_episode_key="uuid-20"
                )
            ),
            1,
        )
        self.assertEqual(
            resolver.get_source_segments_by_anchor(
                "amdb:101", source_episode_key="uuid-30"
            ),
            [],
        )
        self.assertEqual(resolver.episode_key_for_anchor(101, 7), None)
        self.assertEqual(resolver.get_segments_by_anchor(101, "ep:7"), [])
        self.assertEqual(inspect_database(compact)["counts"]["source_title_refs"], 2)
        audit = audit_runtime(compact)
        self.assertEqual(audit["title_only_titles"], 2)
        self.assertEqual(audit["linked_source_segments"], 2)
        self.assertEqual(audit["source_title_refs_by_source"], {"anime-skip-api": 2})
        # A source-only fixture deliberately has no canonical segments; the
        # overall database audit requires at least one real canonical segment.
        self.assertFalse(audit["ok"])
        result = StringIO()
        with redirect_stdout(result):
            self.assertEqual(
                main(["source-anchor", "--db", str(compact), "--anchor", "amdb:101"]), 0
            )
        self.assertEqual(json.loads(result.getvalue())[0]["source_title_key"], "20")
        result = StringIO()
        with redirect_stdout(result):
            self.assertEqual(
                main(
                    [
                        "source-anchor",
                        "--db",
                        str(compact),
                        "--anchor",
                        "101",
                        "--title-refs",
                    ]
                ),
                0,
            )
        self.assertEqual(
            json.loads(result.getvalue())[0]["identity_method"], "exact-anilist-id"
        )

    def test_same_source_title_cannot_change_amdb_anchor(self) -> None:
        with DatabaseWriter(self.runtime, self.evidence) as writer:
            source = writer.source_id(ANIME_SKIP_API)
            writer.add_source_title_ref(
                source_id=source,
                source_title_key="20",
                anchor_id=101,
                identity_method="exact-anilist-id",
            )
            with self.assertRaises(IdentityConflict):
                writer.add_source_title_ref(
                    source_id=source,
                    source_title_key="20",
                    anchor_id=303,
                    identity_method="exact-anilist-id",
                )
            self.assertEqual(
                writer.conn.execute(
                    "SELECT anchor_id FROM source_title_refs"
                ).fetchall(),
                [(101,)],
            )

    def test_invalid_or_missing_records_do_not_create_ghost_titles(self) -> None:
        invalid = {**self.row("30"), "start_ms": -1}
        path = self.checkpoint(
            {
                "20": {"status": "missing", "segments": [self.row("20")]},
                "30": {"status": "found", "segments": [invalid]},
            }
        )
        with (
            MappingAnchorIndex(self.mapping) as identities,
            DatabaseWriter(self.runtime, self.evidence) as writer,
        ):
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            stats = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
            )
            self.assertEqual(stats.runtime_segments, 0)
            self.assertEqual(stats.source_only_segments, 0)
            self.assertEqual(
                writer.conn.execute("SELECT count(*) FROM titles").fetchone()[0], 0
            )
            self.assertEqual(
                writer.conn.execute(
                    "SELECT count(*) FROM source_title_refs"
                ).fetchone()[0],
                0,
            )

    def test_runtime_audit_catches_wrong_source_title_episode_link(self) -> None:
        with DatabaseWriter(self.runtime, self.evidence) as writer:
            src = writer.source_id(ANIME_SKIP_API)
            writer.add_source_title_ref(
                source_id=src,
                source_title_key="20",
                anchor_id=101,
                identity_method="exact-anilist-id",
            )
            writer.get_or_create_title(303)
            ep = writer.get_or_create_episode(303, episode_key="ep:1", episode_number=1)
            writer.add_episode_ref(
                src,
                source_title_key="20",
                source_episode_key="uuid-bad",
                episode_id=ep,
            )
            writer.add_segment(
                episode_id=ep,
                source_id=src,
                lineage_id=writer.lineage_id("anime-skip", "Anime Skip"),
                source_segment_id="seg",
                segment_type="opening",
                start_ms=10,
                end_ms=100,
            )
        audit = audit_runtime(self.runtime)
        self.assertEqual(audit["source_title_ref_mismatches"], 1)
        self.assertFalse(audit["ok"])


if __name__ == "__main__":
    unittest.main()
