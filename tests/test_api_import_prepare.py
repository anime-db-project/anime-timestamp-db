"""Offline regression tests for the all-or-nothing API import gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import api_import_prepare


class ApiImportPrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    @staticmethod
    def fake_restore_for(available: set[str]):
        def fake_restore(source: str, target: Path) -> dict:
            if source not in available:
                return {"restored": False, "source": source}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"validated fixture")
            return {"restored": True, "source": source}

        return fake_restore

    def test_both_ready_enables_import(self) -> None:
        with mock.patch.object(
            api_import_prepare,
            "restore",
            side_effect=self.fake_restore_for({"aniskip", "anime_skip"}),
        ):
            result = api_import_prepare.prepare_api_import(self.root)
        self.assertTrue(result["enabled"])
        self.assertEqual(result["sources"], {"aniskip": "ready", "anime_skip": "ready"})

    def test_bootstrap_without_checkpoints_keeps_static_build(self) -> None:
        with mock.patch.object(
            api_import_prepare,
            "restore",
            side_effect=self.fake_restore_for(set()),
        ):
            result = api_import_prepare.prepare_api_import(self.root)
        self.assertFalse(result["enabled"])
        self.assertEqual(set(result["sources"].values()), {"pending"})

    def test_one_checkpoint_never_triggers_partial_import(self) -> None:
        with mock.patch.object(
            api_import_prepare,
            "restore",
            side_effect=self.fake_restore_for({"aniskip"}),
        ):
            result = api_import_prepare.prepare_api_import(self.root)
        self.assertFalse(result["enabled"])
        self.assertEqual(
            result["sources"], {"aniskip": "ready", "anime_skip": "pending"}
        )

    def test_stale_local_checkpoint_does_not_enable_import(self) -> None:
        stale = self.root / "anime_skip.json.gz"
        stale.write_bytes(b"stale")
        with mock.patch.object(
            api_import_prepare,
            "restore",
            side_effect=self.fake_restore_for({"aniskip"}),
        ):
            result = api_import_prepare.prepare_api_import(self.root)
        self.assertFalse(result["enabled"])
        self.assertFalse(stale.exists())

    def test_restored_checkpoint_missing_is_fatal(self) -> None:
        with mock.patch.object(
            api_import_prepare, "restore", return_value={"restored": True}
        ):
            with self.assertRaisesRegex(RuntimeError, "checkpoint is absent"):
                api_import_prepare.prepare_api_import(self.root)

    def test_corrupted_checkpoint_is_fatal(self) -> None:
        with mock.patch.object(
            api_import_prepare,
            "restore",
            side_effect=ValueError("Corrupted checkpoint"),
        ):
            with self.assertRaisesRegex(ValueError, "Corrupted checkpoint"):
                api_import_prepare.prepare_api_import(self.root)


if __name__ == "__main__":
    unittest.main()
