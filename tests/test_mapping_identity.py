from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import zstandard as zstd

from _mapping_fixture import create_mapping_db
from anime_timestamp_db.mapping_identity import (
    AnchorResolutionConflict,
    MappingAnchorIndex,
    decompress_mapping_database,
    mapping_database_metadata,
)


class MappingIdentityTests(unittest.TestCase):
    def test_decompresses_and_resolves_stable_anchor_without_copying_aliases(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "mappings.db"
            compressed = root / "mappings.db.zst"
            unpacked = root / "unpacked.db"
            create_mapping_db(
                raw,
                nodes=[
                    (1, "mal", "1"),
                    (2, "anilist", "101"),
                    (3, "anidb", "301"),
                ],
                anchors={7001: [1, 2, 3]},
            )
            compressor = zstd.ZstdCompressor(level=1)
            with raw.open("rb") as src, compressed.open("wb") as dst:
                compressor.copy_stream(src, dst)

            self.assertEqual(
                decompress_mapping_database(compressed, unpacked), unpacked
            )
            metadata = mapping_database_metadata(unpacked)
            self.assertEqual(metadata["anchor_schema_version"], "1")
            self.assertEqual(metadata["anchor_namespace"], "amdb")

            with MappingAnchorIndex(unpacked) as identities:
                self.assertEqual(identities.anchor_for("mal", "1"), 7001)
                self.assertEqual(
                    identities.anchor_for_ids({"mal": "1", "anilist": "101"}),
                    7001,
                )
                self.assertEqual(
                    identities.ids_for_anchor("amdb:7001"),
                    {"anidb": ["301"], "anilist": ["101"], "mal": ["1"]},
                )

    def test_conflicting_known_ids_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mappings.db"
            create_mapping_db(
                path,
                nodes=[(1, "mal", "1"), (2, "anilist", "2")],
                anchors={100: [1], 200: [2]},
            )
            with MappingAnchorIndex(path) as identities:
                with self.assertRaises(AnchorResolutionConflict):
                    identities.anchor_for_ids({"mal": "1", "anilist": "2"})


if __name__ == "__main__":
    unittest.main()
