"""Offline, bounded tests for new source adapters, pacing and checkpoint recovery."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest import mock

import httpx

from anime_timestamp_db.config import EXTERNAL_API_SPECS
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.external_importer import import_external_checkpoint
from anime_timestamp_db.mapping_identity import MappingAnchorIndex
from scripts import crawl_timestamps
from scripts.external_sources import make_request, parse_segments
from scripts.source_policies import PacedLimiter, SourcePolicy, load_policies
from tests._mapping_fixture import create_mapping_db


class ExternalAdapterTests(unittest.TestCase):
    def test_four_provider_parsers_and_provenance(self) -> None:
        samples = {
            "introdb": (
                {
                    "intro": {"start_ms": 10000, "end_ms": 90000},
                    "outro": {"start_ms": 1300000, "end_ms": 1400000},
                    "recap": None,
                    "post_credits": None,
                },
                "imdb",
                "tt1234",
            ),
            "publicmetadb": (
                {
                    "intro_start_ms": 10000,
                    "intro_end_ms": 85000,
                    "credits_start_ms": 1400000,
                },
                "tmdb_tv",
                "999",
            ),
            "theintrodb": (
                {
                    "intro": [{"start_ms": 0, "end_ms": 80000}],
                    "credits": [{"start_ms": 1300000, "end_ms": None}],
                    "recap": [],
                },
                "tvdb",
                "100",
            ),
            "introhater": (
                [
                    {
                        "start": 4.5,
                        "end": 91.7,
                        "label": "Intro",
                        "source": "aniskip",
                        "videoId": "tt1234:1:1",
                    },
                    {"start": 400, "end": 380, "label": "Credits"},
                ],
                "imdb",
                "tt1234",
            ),
        }
        expected = {"introdb": 2, "publicmetadb": 1, "theintrodb": 1, "introhater": 1}
        for source, (data, provider, native_id) in samples.items():
            with self.subTest(source=source):
                got = parse_segments(
                    source,
                    data,
                    provider=provider,
                    title_id=native_id,
                    season=1,
                    episode=1,
                )
                self.assertEqual(len(got), expected[source])
                self.assertTrue(all(not r["episode_identity_proven"] for r in got))
                self.assertTrue(all(r["start_ms"] < r["end_ms"] for r in got))
                if source == "introhater":
                    self.assertEqual(got[0]["upstream_lineage"], "aniskip")

    def test_endpoints_and_keys_are_allowlisted(self) -> None:
        url, h, p = make_request("theintrodb", "tvdb", "76885", 1, 1)
        self.assertEqual(url, "https://api.theintrodb.org/v4/media")
        self.assertEqual(p["tvdb_id"], "76885")
        self.assertNotIn("Authorization", h)
        _, h, p = make_request(
            "publicmetadb",
            "tmdb_tv",
            "1399",
            1,
            2,
            api_key="test-token",
        )
        self.assertEqual(h, {"Authorization": "Bearer test-token"})
        self.assertEqual(p["tmdb_id"], "1399")
        for source, provider in (("introdb", "imdb"), ("introhater", "imdb")):
            url, _headers, params = make_request(source, provider, "tt1234", 1, 3)
            self.assertIn("intro", url)
            if source == "introhater":
                self.assertTrue(url.endswith("tt1234:1:3"))
            else:
                self.assertEqual(params["imdb_id"], "tt1234")
        with self.assertRaises(ValueError):
            make_request("introhater", "imdb", "../../admin", 1, 1)
        with self.assertRaises(ValueError):
            make_request("publicmetadb", "tmdb_tv", "9", 1, 1)

    def test_profiles_per_second_minute_hour_and_run(self) -> None:
        policies = load_policies()
        self.assertEqual(
            set(policies),
            {
                "aniskip",
                "anime_skip",
                "theintrodb",
                "publicmetadb",
                "introdb",
                "introhater",
            },
        )
        self.assertTrue(all(p.max_requests == 2000 for p in policies.values()))
        self.assertLess(policies["theintrodb"].per_second, 3)
        self.assertLess(policies["theintrodb"].per_minute, 180)
        self.assertLess(policies["introhater"].per_hour, 5000)
        self.assertTrue(policies["introdb"].requires_bulk_permission)
        self.assertTrue(policies["introhater"].requires_bulk_permission)
        for p in policies.values():
            self.assertLess(p.delay_seconds[0], p.delay_seconds[1])
            self.assertLess(p.per_minute, p.per_hour)

    def test_sliding_windows_are_enforced_in_fake_clock(self) -> None:
        # Virtual time: no actual traffic and no waiting for an hour.
        clock = [0.0]
        seen = []

        async def fake_sleep(seconds):
            clock[0] += seconds

        policy = SourcePolicy(
            source="fixture",
            max_requests=5,
            per_second=1,
            per_minute=2,
            per_hour=3,
            delay_seconds=(0.1, 0.3),
            retry_429_wait_seconds=1,
            max_429_wait_seconds=2,
            requires_bulk_permission=False,
        )
        limiter = PacedLimiter(policy, jitter=False)

        async def go():
            for _ in range(5):
                await limiter.wait()
                seen.append(clock[0])

        with (
            mock.patch(
                "scripts.source_policies.time.monotonic", side_effect=lambda: clock[0]
            ),
            mock.patch("scripts.source_policies.asyncio.sleep", fake_sleep),
        ):
            asyncio.run(go())
        self.assertGreaterEqual(seen[1] - seen[0], 1)
        self.assertGreaterEqual(seen[2] - seen[0], 60)
        self.assertGreaterEqual(seen[3] - seen[0], 3600)

    def test_429_once_retries_then_stops_without_losing_previous_data(self) -> None:
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            m = root / "mappings.db"
            create_mapping_db(
                m,
                nodes=[(1, "tvdb", "76885")],
                anchors={101: [1]},
            )
            args = argparse.Namespace(
                source="theintrodb",
                mapping_db=m,
                timestamps_db=None,
                state_dir=root / "state",
                output_dir=root / "out",
                max_requests=4,
                rpm=None,
                max_episodes=3,
                unknown_episodes=3,
                positive_ttl_days=30,
                negative_ttl_days=14,
                only_anchor=101,
                dry_run=False,
                export_only=False,
            )
            number = [0]

            def handler(req):
                number[0] += 1
                if number[0] == 1:
                    return httpx.Response(
                        200,
                        json={
                            "intro": [{"start_ms": 1000, "end_ms": 90000}],
                            "credits": [],
                        },
                    )
                return httpx.Response(
                    429, json={"error": "limited"}, headers={"Retry-After": "1"}
                )

            class NoWait:
                async def wait(self):
                    pass

            async def no_sleep(_s):
                pass

            async def run():
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(handler)
                ) as client:
                    with (
                        mock.patch(
                            "scripts.crawl_external.PacedLimiter", return_value=NoWait()
                        ),
                        mock.patch("scripts.crawl_timestamps.asyncio.sleep", no_sleep),
                    ):
                        return await crawl_timestamps.crawl(args, client=client)

            report, ok = asyncio.run(run())
            self.assertTrue(ok)
            self.assertEqual(report["stopped_reason"], "rate_limited_after_retry")
            self.assertEqual(report["found"], 1)
            self.assertEqual(report["attempted"], 1)
            self.assertEqual(number[0], 3)
            state = crawl_timestamps.load_state(
                root / "state" / "theintrodb.json.gz", "theintrodb"
            )
            self.assertEqual(len(state["records"]), 1)
            self.assertEqual(report["observations"], 1)
            self.assertTrue((root / "out" / "theintrodb.jsonl.gz").is_file())

    def test_per_source_live_client_mock_and_safe_external_import(self) -> None:
        payloads = {
            "theintrodb": (
                {"intro": [{"start_ms": 1000, "end_ms": 90000}]},
                "tvdb",
                "100",
            ),
            "publicmetadb": (
                {"intro_start_ms": 1000, "intro_end_ms": 90000},
                "tmdb_tv",
                "200",
            ),
            "introdb": (
                {"intro": {"start_ms": 1000, "end_ms": 90000}},
                "imdb",
                "tt1234",
            ),
            "introhater": (
                [{"start": 1, "end": 90, "label": "Intro"}],
                "imdb",
                "tt1234",
            ),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mapping = root / "mappings.db"
            create_mapping_db(
                mapping,
                nodes=[
                    (1, "tvdb", "100"),
                    (2, "tmdb_tv", "200"),
                    (3, "imdb", "tt1234"),
                ],
                anchors={101: [1, 2, 3]},
            )

            async def mock_one(source, payload):
                args = argparse.Namespace(
                    source=source,
                    mapping_db=mapping,
                    timestamps_db=None,
                    state_dir=root / f"state-{source}",
                    output_dir=root / f"out-{source}",
                    max_requests=1,
                    rpm=None,
                    max_episodes=1,
                    unknown_episodes=1,
                    positive_ttl_days=30,
                    negative_ttl_days=14,
                    only_anchor=101,
                    dry_run=False,
                    export_only=False,
                    publicmetadb_api_key="dummy-key",
                )
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(
                        lambda req: httpx.Response(200, json=payload)
                    )
                ) as client:
                    return await crawl_timestamps.crawl(args, client=client)

            for source, (payload, _provider, _id) in payloads.items():
                with (
                    self.subTest(source=source),
                    mock.patch.dict(
                        "os.environ",
                        {
                            "BULK_SOURCE_PERMISSION_INTRODB": "true",
                            "BULK_SOURCE_PERMISSION_INTROHATER": "true",
                        },
                    ),
                ):
                    report, ok = asyncio.run(mock_one(source, payload))
                    self.assertTrue(ok)
                    self.assertEqual(report["observations"], 1)
                    state_path = root / f"state-{source}" / f"{source}.json.gz"
                    with (
                        MappingAnchorIndex(mapping) as identities,
                        DatabaseWriter(
                            root / f"{source}.db", root / f"{source}-evidence.db"
                        ) as writer,
                    ):
                        snap = writer.add_snapshot(
                            EXTERNAL_API_SPECS[source],
                            type(
                                "Download",
                                (),
                                {
                                    "source_url": "fixture",
                                    "final_url": "fixture",
                                    "sha256": "a" * 64,
                                    "size_bytes": 1,
                                    "retrieved_at": "2026-11-06T00:00:00+00:00",
                                    "etag": "",
                                    "last_modified": "",
                                },
                            )(),
                        )
                        stat = import_external_checkpoint(
                            state_path,
                            source=source,
                            writer=writer,
                            snapshot_id=snap,
                            identities=identities,
                        )
                        self.assertEqual(stat.source_only_segments, 1)
                        self.assertEqual(
                            writer.conn.execute(
                                "select count(*) from episodes"
                            ).fetchone()[0],
                            0,
                        )
                        self.assertEqual(
                            writer.conn.execute(
                                "select count(*) from source_title_refs"
                            ).fetchone()[0],
                            1,
                        )
            # Keyless publicmeta and unauthorized sources fail closed.
            with mock.patch.dict("os.environ", {}, clear=True):
                args = argparse.Namespace(
                    source="introhater",
                    mapping_db=mapping,
                    dry_run=False,
                    export_only=False,
                    publicmetadb_api_key="",
                    state_dir=root / "x",
                    output_dir=root / "y",
                    max_requests=1,
                    max_episodes=1,
                    unknown_episodes=1,
                    only_anchor=101,
                )
                with self.assertRaises(ValueError):
                    asyncio.run(crawl_timestamps.crawl(args))


if __name__ == "__main__":
    unittest.main()
