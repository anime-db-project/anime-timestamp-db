from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anime_timestamp_db.source_archives import (
    append_checksum_rows,
    archive_set,
    validate_release_token,
)


class SourceArchiveContractTests(unittest.TestCase):
    def test_archive_names_keep_zz_only_outside_normal_root(self) -> None:
        archives = archive_set("anime-timestamp-db", "v0.4.0", Path("artifacts"))
        self.assertEqual(archives.root_name, "anime-timestamp-db-v0.4.0")
        self.assertEqual(
            [path.name for path in archives.paths],
            [
                "zz-anime-timestamp-db-v0.4.0-source.7z",
                "zz-anime-timestamp-db-v0.4.0-source.tar.zst",
                "zz-anime-timestamp-db-v0.4.0-source.zip",
            ],
        )

    def test_release_tokens_reject_paths_and_shell_metacharacters(self) -> None:
        for value in ("../v1", "v1/evil", "v1 bad", "v1;rm", "-v1", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_release_token(value, field="tag")

    def test_checksum_rows_are_idempotently_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "zz-project-v1-source.7z"
            second = root / "zz-project-v1-source.zip"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            sums = root / "SHA256SUMS"
            sums.write_text(
                "abc  runtime.db\nold  zz-project-v1-source.7z\n", encoding="utf-8"
            )

            append_checksum_rows(sums, (first, second))
            append_checksum_rows(sums, (first, second))
            rows = sums.read_text(encoding="utf-8").splitlines()

            self.assertEqual(rows[0], "abc  runtime.db")
            self.assertEqual(sum(first.name in row for row in rows), 1)
            self.assertEqual(sum(second.name in row for row in rows), 1)

    def test_release_workflow_calls_tested_packager_before_checksum_verification(
        self,
    ) -> None:
        workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
        package = "python -m anime_timestamp_db.source_archives"
        verify = "sha256sum --check SHA256SUMS"
        publish = 'gh release create "$tag"'
        self.assertIn(package, workflow)
        self.assertIn("--checksums artifacts/SHA256SUMS", workflow)
        self.assertLess(workflow.index(package), workflow.index(verify))
        self.assertLess(workflow.index(verify), workflow.index(publish))


if __name__ == "__main__":
    unittest.main()
