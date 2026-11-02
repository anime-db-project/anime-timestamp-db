from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from anime_timestamp_db.database import (
    create_evidence_database,
    create_runtime_database,
    inspect_database,
)
from anime_timestamp_db.schema import SCHEMA_VERSION


class DatabaseSchemaTests(unittest.TestCase):
    def test_runtime_database_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps.db"
            create_runtime_database(path)
            info = inspect_database(path)

            self.assertEqual(info["metadata"]["database_role"], "runtime")
            self.assertEqual(info["metadata"]["schema_version"], str(SCHEMA_VERSION))
            self.assertEqual(info["counts"]["segments"], 0)
            self.assertEqual(info["counts"]["consensus_segments"], 0)

            with sqlite3.connect(path) as conn:
                user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(user_version, SCHEMA_VERSION)

    def test_evidence_database_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps-evidence.db"
            create_evidence_database(path)
            info = inspect_database(path)

            self.assertEqual(info["metadata"]["database_role"], "evidence")
            self.assertEqual(info["counts"]["source_snapshots"], 0)
            self.assertEqual(info["counts"]["records"], 0)
            self.assertEqual(info["counts"]["record_segments"], 0)

    def test_existing_database_is_not_overwritten_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps.db"
            create_runtime_database(path)
            with self.assertRaises(FileExistsError):
                create_runtime_database(path)
            create_runtime_database(path, overwrite=True)

    def test_segment_constraints_reject_invalid_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timestamps.db"
            create_runtime_database(path)
            with sqlite3.connect(path) as conn:
                conn.execute("PRAGMA foreign_keys=ON")
                source_id = conn.execute(
                    "INSERT INTO sources(source_key, display_name) VALUES('demo', 'Demo')"
                ).lastrowid
                lineage_id = conn.execute(
                    "INSERT INTO lineages(lineage_key, display_name) VALUES('demo', 'Demo')"
                ).lastrowid
                title_id = conn.execute(
                    "INSERT INTO titles(canonical_provider, canonical_id) VALUES('mal', '1')"
                ).lastrowid
                episode_id = conn.execute(
                    "INSERT INTO episodes(title_id, episode_key) VALUES(?, 'ep:1')",
                    (title_id,),
                ).lastrowid

                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO segments(
                            episode_id, source_id, lineage_id,
                            segment_type, start_ms, end_ms
                        ) VALUES (?, ?, ?, 'opening', 1000, 1000)
                        """,
                        (episode_id, source_id, lineage_id),
                    )


if __name__ == "__main__":
    unittest.main()
