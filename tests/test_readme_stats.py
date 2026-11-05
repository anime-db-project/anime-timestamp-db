from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.benchmark_lookup import percentile
from scripts.update_readme_stats import BEGIN, END, LANGUAGES, WORDS, update_readmes


class TimestampReadmeStatisticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "docs").mkdir()
        for lang in LANGUAGES:
            target = self.root / (
                "README.md" if lang == "en" else f"docs/README.{lang}.md"
            )
            target.write_text(
                f"# Example\n\n## {WORDS[lang]['title']}\n\nOld stats\n\n## Features\n\nDo not modify.\n",
                encoding="utf-8",
            )
        self.manifest = {
            "generated_at": "2026-11-05T19:21:34+00:00",
            "audit": {
                "ok": True,
                "runtime": {
                    "counts": {
                        "titles": 32,
                        "episodes": 123,
                        "segments": 456,
                        "source_segments": 78,
                        "consensus_segments": 90,
                        "consensus_members": 144,
                    }
                },
                "evidence": {"counts": {"records": 204, "source_snapshots": 8}},
            },
            "artifacts": {
                "timestamps.db": {"size_bytes": 2048},
                "timestamps.db.zst": {"size_bytes": 1024},
            },
        }
        self.performance = {
            "database_bytes": 2048,
            "sampled_episodes": 20,
            "rounds": 2,
            "environment": "Linux / Python 3.12",
            "normalized_lookup": {
                "median_ms": 0.42,
                "p95_ms": 1.0,
                "p99_ms": 1.2,
                "lookups_per_second": 1900,
            },
            "consensus_lookup": {
                "median_ms": 0.28,
                "p95_ms": 0.7,
                "p99_ms": 0.9,
                "lookups_per_second": 2500,
            },
        }

    def test_all_locales_and_idempotence(self) -> None:
        changed = update_readmes(
            self.root, self.manifest, self.performance, "v2026.11.05.1"
        )
        self.assertEqual(len(changed), 7)
        for lang in LANGUAGES:
            target = self.root / (
                "README.md" if lang == "en" else f"docs/README.{lang}.md"
            )
            content = target.read_text(encoding="utf-8")
            self.assertIn(BEGIN, content)
            self.assertIn(END, content)
            self.assertIn("**456**", content)
            self.assertIn("**0.420 ms**", content)
            self.assertNotIn("database build:", content)
            self.assertNotIn("Загрузка источников и сборка БД:", content)
            self.assertIn("Do not modify.", content)
            self.assertNotIn("Old stats", content)
        self.assertEqual(
            update_readmes(self.root, self.manifest, self.performance, "v2026.11.05.1"),
            [],
        )

    def test_new_stats_and_release_tag(self) -> None:
        update_readmes(self.root, self.manifest, self.performance, "v2026.11.05.1")
        update = {**self.manifest}
        update["audit"] = {
            **self.manifest["audit"],
            "runtime": {
                "counts": {
                    **self.manifest["audit"]["runtime"]["counts"],
                    "segments": 999,
                }
            },
        }
        self.assertEqual(
            len(
                update_readmes(
                    self.root, update, self.performance, "v2026.11.06.1", check=True
                )
            ),
            7,
        )

    def test_invalid_benchmark_and_failed_audit(self) -> None:
        bad = {**self.performance, "database_bytes": 99}
        with self.assertRaises(ValueError):
            update_readmes(self.root, self.manifest, bad, "v2026.11.05.1")
        failed = {**self.manifest, "audit": {**self.manifest["audit"], "ok": False}}
        with self.assertRaises(ValueError):
            update_readmes(self.root, failed, None, "v2026.11.05.1")
        self.assertNotIn(BEGIN, (self.root / "README.md").read_text())

    def test_percentile(self) -> None:
        self.assertEqual(percentile([10.0, 20.0, 30.0], 0.5), 20.0)
        self.assertEqual(percentile([10.0, 20.0, 30.0], 0.95), 30.0)


if __name__ == "__main__":
    unittest.main()
