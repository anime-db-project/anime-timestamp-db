from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.bootstrap_progress import bootstrap_plan


class BootstrapProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def report(
        self,
        source: str,
        *,
        unseen: int,
        attempted: int = 1000,
        errors: list | None = None,
        nested: bool = False,
    ) -> None:
        folder = self.root / source
        if nested:
            folder = folder / "crawler-output"
        folder.mkdir(parents=True)
        (folder / f"{source}-report.json").write_text(
            json.dumps(
                {
                    "source": source,
                    "attempted": attempted,
                    "initial_unchecked_after_run": unseen,
                    "errors": errors or [],
                }
            )
        )

    def test_nested_and_flattened_artifacts_continue(self) -> None:
        self.report("aniskip", unseen=2000, nested=True)
        self.report("anime_skip", unseen=0)
        result = bootstrap_plan(self.root, 160)
        self.assertEqual(result["continue"], "true")
        self.assertEqual(result["next_runs"], 159)
        self.assertEqual(result["unseen_aniskip"], 2000)
        self.assertEqual(result["unseen_anime_skip"], 0)

    def test_completion_and_safety_budget(self) -> None:
        self.report("aniskip", unseen=123)
        self.report("anime_skip", unseen=0)
        self.assertEqual(bootstrap_plan(self.root, 1)["continue"], "false")
        with self.assertRaises(ValueError):
            bootstrap_plan(self.root, 161)
        with self.assertRaises(ValueError):
            bootstrap_plan(self.root, 0)

    def test_missing_report_and_duplicate_is_fatal(self) -> None:
        self.report("aniskip", unseen=1)
        with self.assertRaisesRegex(ValueError, "Expected exactly one anime_skip"):
            bootstrap_plan(self.root, 3)
        self.report("anime_skip", unseen=1)
        self.report("aniskip", unseen=1, nested=True)
        with self.assertRaisesRegex(ValueError, "Expected exactly one aniskip"):
            bootstrap_plan(self.root, 3)

    def test_fatal_source_or_no_progress_stops_chain(self) -> None:
        self.report("aniskip", unseen=2, attempted=0)
        self.report("anime_skip", unseen=1)
        with self.assertRaisesRegex(ValueError, "stalled"):
            bootstrap_plan(self.root, 3)

    def test_real_api_error_stops_chain(self) -> None:
        self.report("aniskip", unseen=2)
        self.report("anime_skip", unseen=5, errors=[{"type": "RateLimited"}])
        with self.assertRaisesRegex(ValueError, "Fatal anime_skip"):
            bootstrap_plan(self.root, 3)


if __name__ == "__main__":
    unittest.main()
