from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from anime_timestamp_db.audit import audit_databases
from anime_timestamp_db.config import SKIPDB
from anime_timestamp_db.consensus import rebuild_consensus
from anime_timestamp_db.database import DatabaseWriter, inspect_database
from anime_timestamp_db.distribution import (
    compact_evidence_database,
    compact_runtime_database,
)
from anime_timestamp_db.resolver import TimestampResolver


class DistributionTests(unittest.TestCase):
    def test_compact_databases_preserve_logical_rows_and_resolver_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            staging_runtime = root / "staging-runtime.db"
            staging_evidence = root / "staging-evidence.db"
            runtime = root / "timestamps.db"
            evidence = root / "timestamps-evidence.db"

            with DatabaseWriter(staging_runtime, staging_evidence) as writer:
                source_id = writer.source_id(SKIPDB)
                lineage_id = writer.lineage_id("skipdb", "SkipDB")
                anchor_id = 42
                writer.get_or_create_title(anchor_id, display_title="Fixture")
                episode_id = writer.get_or_create_episode(
                    anchor_id,
                    episode_key="ep:1",
                    episode_number=1,
                    duration_ms=1_440_000,
                )
                writer.add_episode_id(
                    episode_id=episode_id,
                    anchor_id=anchor_id,
                    provider="mal",
                    episode_number=1,
                )
                writer.add_episode_ref(
                    source_id,
                    source_title_key="fixture-title",
                    source_episode_key="fixture-episode",
                    episode_id=episode_id,
                    source_episode_number_text="1",
                )
                writer.add_segment(
                    episode_id=episode_id,
                    source_id=source_id,
                    lineage_id=lineage_id,
                    source_segment_id="segment:1",
                    segment_type="opening",
                    start_ms=10_000,
                    end_ms=100_000,
                    media_duration_ms=1_440_000,
                    mapping_method="exact-single-bridge",
                    mapping_confidence=0.98,
                    votes_up=3,
                )
                writer.add_source_segment(
                    source_id=source_id,
                    lineage_id=lineage_id,
                    source_title_key="source-only-title",
                    source_episode_key="source-only-episode",
                    source_segment_id="source-only:1",
                    segment_type="ending",
                    start_ms=1_300_000,
                    end_ms=1_390_000,
                )
                rebuild_consensus(writer.conn)

                snapshot_id = writer.add_snapshot(
                    SKIPDB,
                    SimpleNamespace(
                        source_url=SKIPDB.url,
                        final_url=SKIPDB.url,
                        sha256="a" * 64,
                        size_bytes=123,
                        retrieved_at="2026-11-03T00:00:00+00:00",
                        etag="",
                        last_modified="",
                    ),
                    metadata={"fixture": True},
                )
                record_id = writer.add_evidence_record(
                    snapshot_id=snapshot_id,
                    record_key="record:1",
                    lineage_key="skipdb",
                    source_title_key="fixture-title",
                    source_episode_key="fixture-episode",
                    source_status="approved",
                    votes_up=3,
                    payload_sha256="b" * 64,
                    normalization_status="mapped",
                    normalization_reason="fixture mapping",
                    normalized_anchor_id=anchor_id,
                    normalized_episode_key="ep:1",
                    metadata={"provider": "fixture"},
                )
                writer.add_evidence_segment(
                    record_id,
                    source_segment_id="segment:1",
                    segment_type="opening",
                    start_ms=10_000,
                    end_ms=100_000,
                    media_duration_ms=1_440_000,
                )
                writer.set_snapshot_record_count(snapshot_id, 1)
                writer.finalize()

            compact_runtime_database(staging_runtime, runtime)
            compact_evidence_database(staging_evidence, evidence)

            report = audit_databases(runtime, evidence)
            self.assertTrue(report["ok"])
            self.assertEqual(
                inspect_database(evidence)["metadata"]["storage_profile"],
                "compact-v1",
            )

            with sqlite3.connect(evidence) as conn:
                relation = conn.execute(
                    "SELECT type FROM sqlite_master WHERE name='records'"
                ).fetchone()
                self.assertEqual(relation, ("view",))
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1
                )
                row = conn.execute(
                    """
                    SELECT record_key, lineage_key, source_title_key,
                           normalization_status, normalization_reason,
                           normalized_anchor_id, normalized_episode_key, metadata_json
                    FROM records
                    """
                ).fetchone()
                self.assertEqual(
                    row,
                    (
                        "record:1",
                        "skipdb",
                        "fixture-title",
                        "mapped",
                        "fixture mapping",
                        42,
                        "ep:1",
                        '{"provider":"fixture"}',
                    ),
                )

            with sqlite3.connect(runtime) as conn:
                indexes = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='index'"
                    )
                }
                self.assertNotIn("episode_ids_episode_idx", indexes)
                self.assertNotIn("episode_refs_episode_idx", indexes)
                self.assertNotIn("consensus_members_segment_idx", indexes)
                self.assertIn("segments_episode_idx", indexes)
                self.assertIn("consensus_episode_idx", indexes)

            resolver = TimestampResolver(runtime)
            self.assertEqual(resolver.episode_key("amdb", "42", 1), "ep:1")
            segment = resolver.get_segments_by_anchor("amdb:42", "ep:1")[0]
            self.assertEqual(segment.mapping_method, "exact-single-bridge")
            self.assertEqual(segment.mapping_confidence, 0.98)
            self.assertEqual(
                resolver.get_consensus_by_anchor("amdb:42", "ep:1")[0].member_count,
                1,
            )
            self.assertEqual(
                resolver.get_source_segments(
                    "skipdb",
                    "source-only-episode",
                    source_title_key="source-only-title",
                )[0].segment_type,
                "ending",
            )


if __name__ == "__main__":
    unittest.main()
