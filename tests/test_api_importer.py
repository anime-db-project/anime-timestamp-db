from __future__ import annotations

import gzip
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.api_importer import import_api_checkpoint
from anime_timestamp_db.build import build_database
from anime_timestamp_db.audit import audit_databases
from anime_timestamp_db.consensus import rebuild_consensus
from anime_timestamp_db.distribution import (
    compact_evidence_database,
    compact_runtime_database,
)
from anime_timestamp_db.config import ANIME_SKIP_API, ANISKIP_API
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.mapping_identity import MappingAnchorIndex
from tests._mapping_fixture import create_mapping_db


class ApiImportTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.mapping = self.root / "mappings.db"
        create_mapping_db(
            self.mapping,
            nodes=[(1, "mal", "5114"), (2, "anilist", "9253")],
            anchors={101: [1, 2]},
        )
        self.download = SimpleNamespace(
            source_url="https://example.invalid/api-state",
            final_url="https://example.invalid/api-state",
            sha256="a" * 64,
            size_bytes=1,
            retrieved_at="2026-11-04T00:00:00+00:00",
            etag="",
            last_modified="",
        )

    def checkpoint(self, source: str, records: dict) -> Path:
        path = self.root / (source + ".json.gz")
        with gzip.open(path, "wt", encoding="utf-8") as file:
            json.dump({"version": 1, "source": source, "records": records}, file)
        return path

    def segment(self, source: str, native_id: str, upstream: str) -> dict:
        return {
            "source": source,
            "native_title_id": native_id,
            "episode": 1,
            "type": "opening",
            "start_ms": 10000,
            "end_ms": 90000,
            "duration_ms": 1500000,
            "source_segment_id": "segment1",
            "upstream_lineage": upstream,
        }

    def test_mal_api_has_same_lineage_as_public_csv(self) -> None:
        row = self.segment("aniskip", "5114", "aniskip")
        path = self.checkpoint(
            "aniskip",
            {
                "5114:1": {
                    "status": "found",
                    "checked_at": "2026-11-04T00:00:00Z",
                    "segments": [row, row],
                }
            },
        )
        with (
            MappingAnchorIndex(self.mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            snapshot = writer.add_snapshot(ANISKIP_API, self.download)
            stats = import_api_checkpoint(
                path,
                source="aniskip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
            )
            self.assertEqual(stats.runtime_segments, 1)
            self.assertEqual(stats.evidence_segments, 1)
            lineage = writer.conn.execute(
                "SELECT lineage_key FROM lineages"
            ).fetchone()[0]
            self.assertEqual(lineage, "aniskip")
            self.assertEqual(
                writer.conn.execute(
                    "SELECT provider,episode_number_text FROM episode_ids"
                ).fetchone(),
                ("mal", "1"),
            )
        with closing(sqlite3.connect(self.root / "runtime.db")) as conn:
            self.assertEqual(
                conn.execute("SELECT anchor_id,episode_key FROM episodes").fetchone(),
                (101, "ep:1"),
            )

    def test_anime_skip_requires_independent_episode_identity(self) -> None:
        row = self.segment("anime_skip", "9253", "BETTER_VRV")
        row.update(
            {
                "episode_identity_proven": True,
                "upstream_episode_id": "upstream-ep",
                "season": 1,
            }
        )
        path = self.checkpoint(
            "anime_skip",
            {"9253": {"status": "found", "segments": [row], "checked_at": "now"}},
        )
        with (
            MappingAnchorIndex(self.mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            # No AniList-native episode index: do not merge with MAL ep:1.
            stats = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
            )
            self.assertEqual(stats.source_only_segments, 1)
            self.assertEqual(stats.runtime_segments, 0)
            self.assertEqual(
                writer.conn.execute(
                    "SELECT source_episode_key FROM source_segments"
                ).fetchone()[0],
                "upstream-ep",
            )
            self.assertEqual(
                writer.conn.execute("SELECT lineage_key FROM lineages").fetchone()[0],
                "better-vrv",
            )

    def test_anime_skip_verified_episode_and_unknown_lineage_are_guarded(self) -> None:
        first = self.segment("anime_skip", "9253", "ANIME_SKIP")
        first.update(
            {
                "episode_identity_proven": True,
                "upstream_episode_id": "episode1",
            }
        )
        second = {
            **first,
            "source_segment_id": "two",
            "upstream_lineage": "UNRECOGNIZED_MIRROR",
            "type": "ending",
        }
        path = self.checkpoint(
            "anime_skip",
            {"9253": {"status": "found", "segments": [first, second]}},
        )
        with (
            MappingAnchorIndex(self.mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            writer.get_or_create_title(101)
            ep = writer.get_or_create_episode(101, episode_key="ep:1", episode_number=1)
            writer.add_episode_id(
                episode_id=ep, anchor_id=101, provider="anilist", episode_number=1
            )
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            stats = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
            )
            self.assertEqual(stats.runtime_segments, 2)
            rows = writer.conn.execute(
                """SELECT lin.lineage_key, s.consensus_eligible
                   FROM segments s JOIN lineages lin ON s.lineage_id=lin.id
                   ORDER BY lin.lineage_key"""
            ).fetchall()
            self.assertEqual(
                rows,
                [("anime-skip", 1), ("anime-skip-unknown", 0)],
            )

    def bridge_fixture(
        self, *, mal_target: str = "5114", ratio: bool = False
    ) -> tuple[Path, AniBridgeIndex]:
        mapping = self.root / "bridge-mappings.db"
        create_mapping_db(
            mapping,
            nodes=[
                (1, "mal", "5114"),
                (2, "anilist", "9253"),
                (3, "anidb", "30"),
            ],
            anchors={101: [1, 2, 3]},
        )
        anilist = {"1": "1"}
        if ratio:
            anilist = {"1": "1-2|2"}
        return mapping, AniBridgeIndex(
            {
                "anidb:30:R": {
                    "anilist:9253": anilist,
                    f"mal:{mal_target}": {"1": "7"},
                }
            }
        )

    def test_anime_skip_bridge_proves_different_mal_episode_number(self) -> None:
        mapping, bridge = self.bridge_fixture()
        first = self.segment("anime_skip", "9253", "ANIME_SKIP")
        first.update(
            episode_identity_proven=True,
            upstream_episode_id="episode-uuid",
            absolute_number=1,
            season=1,
        )
        second = {**first, "source_segment_id": "segment2", "type": "ending"}
        path = self.checkpoint(
            "anime_skip", {"9253": {"status": "found", "segments": [first, second]}}
        )
        with (
            MappingAnchorIndex(mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            result = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
                anibridge=bridge,
            )
            self.assertEqual(result.runtime_segments, 2)
            self.assertEqual(result.source_only_segments, 0)
            self.assertEqual(result.runtime_segments_exact, 2)
            self.assertEqual(result.exact_episode_mappings, 1)
            self.assertEqual(
                writer.conn.execute(
                    "SELECT anchor_id, episode_key FROM episodes"
                ).fetchone(),
                (101, "ep:7"),
            )
            self.assertEqual(
                writer.conn.execute(
                    "SELECT provider, scope, episode_number_text FROM episode_ids"
                    " ORDER BY provider"
                ).fetchall(),
                [("anidb", "R", "1"), ("anilist", "", "1"), ("mal", "", "7")],
            )
            self.assertEqual(
                writer.conn.execute(
                    "SELECT DISTINCT mapping_method FROM segments"
                ).fetchall(),
                [("exact-anibridge-api",)],
            )
            self.assertEqual(
                writer.conn.execute("SELECT COUNT(*) FROM episode_refs").fetchone()[0],
                1,
            )
            evidence = writer.evidence.execute(
                "SELECT metadata_json FROM records LIMIT 1"
            ).fetchone()
            self.assertEqual(json.loads(evidence[0])["bridge_proof"]["mal_episode"], 7)

    def test_anime_skip_bridge_requires_usable_native_identity(self) -> None:
        mapping, bridge = self.bridge_fixture()
        row = self.segment("anime_skip", "9253", "ANIME_SKIP")
        row.update(
            episode_identity_proven=False,
            upstream_episode_id="season-two-local-number",
            season=2,
            absolute_number=None,
        )
        path = self.checkpoint(
            "anime_skip", {"9253": {"status": "found", "segments": [row]}}
        )
        with (
            MappingAnchorIndex(mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            result = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
                anibridge=bridge,
            )
            self.assertEqual(result.source_only_segments, 1)
            self.assertEqual(result.runtime_segments, 0)
            self.assertEqual(
                writer.conn.execute("SELECT count(*) FROM titles").fetchone()[0], 0
            )

    def test_anime_skip_bridge_conflicting_uuids_stay_source_only(self) -> None:
        mapping, bridge = self.bridge_fixture()
        row = self.segment("anime_skip", "9253", "ANIME_SKIP")
        row.update(episode_identity_proven=True, upstream_episode_id="uuid-a")
        other = {
            **row,
            "source_segment_id": "different",
            "upstream_episode_id": "uuid-b",
        }
        path = self.checkpoint(
            "anime_skip", {"9253": {"status": "found", "segments": [row, other]}}
        )
        with (
            MappingAnchorIndex(mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            result = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
                anibridge=bridge,
            )
            self.assertEqual(result.source_only_segments, 2)
            self.assertEqual(result.runtime_segments, 0)

    def test_anime_skip_bridge_rejects_conflicting_existing_index(self) -> None:
        mapping, bridge = self.bridge_fixture()
        row = self.segment("anime_skip", "9253", "ANIME_SKIP")
        row.update(episode_identity_proven=True, upstream_episode_id="uuid-a")
        path = self.checkpoint(
            "anime_skip", {"9253": {"status": "found", "segments": [row]}}
        )
        with (
            MappingAnchorIndex(mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            writer.get_or_create_title(101)
            existing = writer.get_or_create_episode(
                101, episode_key="ep:8", episode_number=8
            )
            writer.add_episode_id(
                episode_id=existing, anchor_id=101, provider="anilist", episode_number=1
            )
            snapshot = writer.add_snapshot(ANIME_SKIP_API, self.download)
            result = import_api_checkpoint(
                path,
                source="anime_skip",
                writer=writer,
                snapshot_id=snapshot,
                identities=identities,
                anibridge=bridge,
            )
            self.assertEqual(result.runtime_segments, 0)
            self.assertEqual(result.source_only_segments, 1)
            self.assertEqual(result.ambiguous, 1)
            self.assertIsNone(
                writer.conn.execute(
                    "SELECT id FROM episodes WHERE episode_key='ep:7'"
                ).fetchone()
            )

    def test_anime_skip_bridge_rejects_other_title_and_ratio(self) -> None:
        # MAL 999 is not a member of the accepted AMDB anchor.
        for mal_target, ratio in (("999", False), ("5114", True)):
            with self.subTest(mal_target=mal_target, ratio=ratio):
                mapping = self.root / f"map-{mal_target}-{ratio}.db"
                create_mapping_db(
                    mapping,
                    nodes=[
                        (1, "mal", "5114"),
                        (2, "anilist", "9253"),
                        (3, "anidb", "30"),
                    ],
                    anchors={101: [1, 2, 3]},
                )
                bridge = AniBridgeIndex(
                    {
                        "anidb:30:R": {
                            "anilist:9253": {"1": "1-2|2" if ratio else "1"},
                            f"mal:{mal_target}": {"1": "7"},
                        }
                    }
                )
                with MappingAnchorIndex(mapping) as identities:
                    from anime_timestamp_db.api_episode_bridge import (
                        AnimeSkipEpisodeBridge,
                    )

                    self.assertIsNone(
                        AnimeSkipEpisodeBridge(bridge, identities).resolve(
                            "9253", 101, 1
                        )
                    )

    def test_api_episode_bridge_rejects_multiple_native_anilist_targets(self) -> None:
        mapping, _bridge = self.bridge_fixture()
        bridge = AniBridgeIndex(
            {
                "anidb:30:R": {
                    "anilist:9253": {"1": "1"},
                    "anilist:999": {"1": "1"},
                    "mal:5114": {"1": "1"},
                }
            }
        )
        with MappingAnchorIndex(mapping) as identities:
            from anime_timestamp_db.api_episode_bridge import AnimeSkipEpisodeBridge

            self.assertIsNone(
                AnimeSkipEpisodeBridge(bridge, identities).resolve("9253", 101, 1)
            )

    def test_api_episode_bridge_rejects_zero_regular_episode(self) -> None:
        mapping, _bridge = self.bridge_fixture()
        bridge = AniBridgeIndex(
            {
                "anidb:30:R": {
                    "anilist:9253": {"0": "1"},
                    "mal:5114": {"0": "1"},
                }
            }
        )
        with MappingAnchorIndex(mapping) as identities:
            from anime_timestamp_db.api_episode_bridge import AnimeSkipEpisodeBridge

            self.assertIsNone(
                AnimeSkipEpisodeBridge(bridge, identities).resolve("9253", 101, 1)
            )

    def test_two_api_sources_survive_compaction_and_full_audit(self) -> None:
        mal = self.segment("aniskip", "5114", "aniskip")
        ani = self.segment("anime_skip", "9253", "ANIME_SKIP")
        ani.update(
            {
                "upstream_episode_id": "ep-a",
                "episode_identity_proven": False,
                "season": 2,
            }
        )
        mal_path = self.checkpoint(
            "aniskip", {"5114:1": {"status": "found", "segments": [mal]}}
        )
        ani_path = self.checkpoint(
            "anime_skip", {"9253": {"status": "found", "segments": [ani]}}
        )
        runtime = self.root / "runtime.db"
        evidence = self.root / "evidence.db"
        with (
            MappingAnchorIndex(self.mapping) as identities,
            DatabaseWriter(runtime, evidence) as writer,
        ):
            one = writer.add_snapshot(ANISKIP_API, self.download)
            two = writer.add_snapshot(ANIME_SKIP_API, self.download)
            mal_stats = import_api_checkpoint(
                mal_path,
                source="aniskip",
                writer=writer,
                snapshot_id=one,
                identities=identities,
            )
            ani_stats = import_api_checkpoint(
                ani_path,
                source="anime_skip",
                writer=writer,
                snapshot_id=two,
                identities=identities,
            )
            self.assertEqual(mal_stats.runtime_segments, 1)
            self.assertEqual(ani_stats.source_only_segments, 1)
            rebuild_consensus(writer.conn)
            writer.finalize()
        compact_runtime = self.root / "compact-runtime.db"
        compact_evidence = self.root / "compact-evidence.db"
        compact_runtime_database(runtime, compact_runtime)
        compact_evidence_database(evidence, compact_evidence)
        report = audit_databases(compact_runtime, compact_evidence)
        self.assertTrue(report["ok"], report)

    def test_bad_checkpoint_and_release_permission_gate(self) -> None:
        path = self.checkpoint("anime_skip", {"9253": {"status": "found"}})
        with (
            MappingAnchorIndex(self.mapping) as identities,
            DatabaseWriter(
                self.root / "runtime.db", self.root / "evidence.db"
            ) as writer,
        ):
            snapshot = writer.add_snapshot(ANISKIP_API, self.download)
            with self.assertRaises(ValueError):
                import_api_checkpoint(
                    path,
                    source="aniskip",
                    writer=writer,
                    snapshot_id=snapshot,
                    identities=identities,
                )
        with self.assertRaisesRegex(ValueError, "not been authorized"):
            build_database(
                self.root / "unused",
                api_checkpoint_dir=self.root,
                allow_api_redistribution=False,
            )


if __name__ == "__main__":
    unittest.main()
