from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.database import (
    create_evidence_database,
    create_runtime_database,
    inspect_database,
)
from anime_timestamp_db.schema import SCHEMA_VERSION


class DatabaseSchemaTests(unittest.TestCase):
    def test_runtime_and_evidence_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "timestamps.db"
            evidence = Path(tmp) / "timestamps-evidence.db"
            create_runtime_database(runtime)
            create_evidence_database(evidence)
            runtime_info = inspect_database(runtime)
            evidence_info = inspect_database(evidence)
            self.assertEqual(runtime_info["metadata"]["database_role"], "runtime")
            self.assertEqual(evidence_info["metadata"]["database_role"], "evidence")
            self.assertEqual(runtime_info["metadata"]["schema_version"], str(SCHEMA_VERSION))
            self.assertEqual(runtime_info["counts"]["source_segments"], 0)
            with closing(sqlite3.connect(runtime)) as conn:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)

    def test_invalid_ranges_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps.db"
            create_runtime_database(path)
            with closing(sqlite3.connect(path)) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
                source = conn.execute(
                    "INSERT INTO sources(source_key, display_name) VALUES('x','X')"
                ).lastrowid
                lineage = conn.execute(
                    "INSERT INTO lineages(lineage_key, display_name) VALUES('x','X')"
                ).lastrowid
                title = conn.execute(
                    "INSERT INTO titles(canonical_provider, canonical_id) VALUES('mal','1')"
                ).lastrowid
                episode = conn.execute(
                    "INSERT INTO episodes(title_id, episode_key) VALUES(?, 'ep:1')",
                    (title,),
                ).lastrowid
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO segments(
                            episode_id, source_id, lineage_id, source_segment_id,
                            segment_type, start_ms, end_ms
                        ) VALUES (?, ?, ?, 'bad', 'opening', 1000, 1000)
                        """,
                        (episode, source, lineage),
                    )


if __name__ == "__main__":
    unittest.main()
