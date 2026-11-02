from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.config import OPEN_ANIME_TIMESTAMPS
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.open_anime_timestamps_importer import (
    import_open_anime_timestamps,
)


class OpenAnimeTimestampsTests(unittest.TestCase):
    def test_imports_anidb_ranges_and_excludes_aggregate_rows_from_consensus(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "timestamps.json"
            source_path.write_text(
                json.dumps(
                    {
                        "1": [
                            {
                                "episode_number": 1,
                                "sources": ["aniskip"],
                                "recap": {"start": -1, "end": -1},
                                "opening": {"start": 10, "end": 100},
                                "ending": {"start": 1300, "end": 1390},
                                "preview_start": 1400,
                            },
                            {
                                "episode_number": 2,
                                "sources": ["aniskip", "open_anime_timestamps"],
                                "recap": {"start": 0, "end": 20},
                                "opening": {"start": 20, "end": 110},
                                "ending": {"start": 1300, "end": 1390},
                                "preview_start": -1,
                            },
                        ]
                    }
                ),
                "utf-8",
            )
            bridge = AniBridgeIndex(
                {
                    "anidb:1:R": {
                        "mal:10": {"1-2": "1-2"},
                        "anilist:20": {"1-2": "1-2"},
                    }
                }
            )
            runtime = root / "runtime.db"
            evidence = root / "evidence.db"
            with DatabaseWriter(runtime, evidence) as writer:
                snapshot = writer.add_snapshot(
                    OPEN_ANIME_TIMESTAMPS,
                    SimpleNamespace(
                        source_url=OPEN_ANIME_TIMESTAMPS.url,
                        final_url=OPEN_ANIME_TIMESTAMPS.url,
                        sha256="abc",
                        size_bytes=source_path.stat().st_size,
                        retrieved_at="2026-11-02T00:00:00+00:00",
                        etag="",
                        last_modified="",
                    ),
                )
                stats = import_open_anime_timestamps(
                    source_path,
                    writer=writer,
                    snapshot_id=snapshot,
                    anibridge=bridge,
                )
                self.assertEqual(stats.records, 2)
                self.assertEqual(stats.runtime_segments, 5)
                self.assertEqual(stats.consensus_eligible_segments, 2)
                self.assertEqual(stats.consensus_excluded_segments, 3)
                self.assertEqual(stats.preview_start_markers, 1)

            with closing(sqlite3.connect(runtime)) as conn:
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM title_ids WHERE provider='anidb' AND external_id='1'"
                    ).fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM episode_ids WHERE provider='anidb' AND scope='R'"
                    ).fetchone()[0],
                    2,
                )
                eligibility = conn.execute(
                    "SELECT consensus_eligible, COUNT(*) FROM segments GROUP BY consensus_eligible ORDER BY consensus_eligible"
                ).fetchall()
                self.assertEqual(eligibility, [(0, 3), (1, 2)])


if __name__ == "__main__":
    unittest.main()
