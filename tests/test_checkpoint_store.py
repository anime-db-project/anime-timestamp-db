from __future__ import annotations

import base64
import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import checkpoint_store as store


class CheckpointStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "anime_skip.json.gz"
        self.data = gzip.compress(
            json.dumps(
                {
                    "version": 1,
                    "source": "anime_skip",
                    "records": {
                        "9253": {"status": "found", "segments": []},
                    },
                }
            ).encode()
        )
        self.state = {"ref": False, "blob": None, "writes": 0}

    def fake_github(self, method: str, endpoint: str, body=None):
        if endpoint.startswith("git/ref/heads/") and method == "GET":
            return {"ref": "valid"} if self.state["ref"] else None
        if endpoint == "git/refs" and method == "POST":
            self.state["ref"] = True
            return {"ref": "valid"}
        if endpoint.startswith("contents/"):
            if method == "GET":
                if self.state["blob"] is None:
                    return None
                return {
                    "content": base64.b64encode(self.state["blob"]).decode("ascii"),
                    "sha": "mocksha",
                }
            if method == "PUT":
                self.state["blob"] = base64.b64decode(body["content"])
                self.state["writes"] += 1
                return {"content": {"sha": "mocksha"}}
        raise AssertionError((method, endpoint))

    def test_action_script_import_works_without_root_on_python_path(self) -> None:
        # GitHub Actions runs checkpoint_store.py as a direct script. Such
        # execution does NOT expose the repository root as a package path.
        script_dir = Path(__file__).resolve().parents[1] / "scripts"
        code = (
            "import sys; sys.path.insert(0, " + repr(str(script_dir)) + "); "
            "from checkpoint_store import _branch; "
            "print(_branch('aniskip'))"
        )
        result = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "crawler-state-aniskip")

    def test_restore_persist_noop_and_backup(self) -> None:
        self.path.write_bytes(self.data)
        env = {"GITHUB_SHA": "a" * 40}
        with (
            patch.dict(os.environ, env),
            patch.object(store, "_github", side_effect=self.fake_github),
        ):
            self.assertFalse(store.restore("anime_skip", self.path)["restored"])
            first = store.persist("anime_skip", self.path)
            self.assertEqual(first["records"], 1)
            self.assertTrue(first["changed"])
            self.assertFalse(store.persist("anime_skip", self.path)["changed"])
            self.assertEqual(self.state["writes"], 1)
            self.path.unlink()
            result = store.restore("anime_skip", self.path)
            self.assertTrue(result["restored"])
            self.assertEqual(self.path.read_bytes(), self.data)

    def test_existing_missing_checkpoint_is_fatal(self) -> None:
        self.state["ref"] = True
        with patch.object(store, "_github", side_effect=self.fake_github):
            with self.assertRaisesRegex(RuntimeError, "refusing to silently restart"):
                store.restore("anime_skip", self.path)

    def test_invalid_source_or_corrupted_data_cannot_be_persisted(self) -> None:
        self.path.write_bytes(self.data)
        with patch.object(store, "_github", side_effect=self.fake_github):
            with self.assertRaises(ValueError):
                store.persist("aniskip", self.path)
            self.path.write_bytes(b"not gzip")
            with self.assertRaisesRegex(ValueError, "Corrupted"):
                store.persist("anime_skip", self.path)


if __name__ == "__main__":
    unittest.main()
