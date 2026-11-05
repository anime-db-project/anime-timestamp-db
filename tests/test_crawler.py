"""Offline fixtures for the two opt-in API crawlers."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import sqlite3
import tempfile
import unittest
from unittest import mock
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import httpx

from anime_timestamp_db.database import create_runtime_database
from scripts import crawl_timestamps as crawl
from tests._mapping_fixture import create_mapping_db


class CrawlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.mapping = self.root / "mappings.db"
        create_mapping_db(
            self.mapping,
            nodes=[
                (1, "mal", "5114"),
                (2, "anilist", "9253"),
                (3, "mal", "21"),
                (4, "anilist", "1055"),
                (5, "mal", "22"),
            ],
            anchors={101: [1, 2], 202: [3, 4], 303: [5]},
        )

    def options(self, source: str, **kwargs: object) -> argparse.Namespace:
        defaults = {
            "source": source,
            "mapping_db": self.mapping,
            "timestamps_db": None,
            "state_dir": self.root / "state",
            "output_dir": self.root / "out",
            "rpm": 70,
            "max_requests": 3,
            "max_episodes": 48,
            "unknown_episodes": 1,
            "positive_ttl_days": 30,
            "negative_ttl_days": 14,
            "anime_skip_url": "https://anime-skip.com/api",
            "anime_skip_client_id": "test-only",
            "dry_run": False,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_catalog_uses_only_confirmed_memberships(self) -> None:
        catalog, stats = crawl.load_catalog(self.mapping)
        self.assertEqual(catalog[101], {"mal": "5114", "anilist": "9253"})
        self.assertEqual(stats["mal_titles"], 3)
        with closing(sqlite3.connect(self.mapping)) as conn:
            conn.execute("INSERT INTO nodes VALUES(6, 'mal', '999')")
            conn.execute("INSERT INTO entity_nodes VALUES(1, 6)")
            conn.commit()
        ambiguous, stats = crawl.load_catalog(self.mapping)
        self.assertNotIn("mal", ambiguous[101])
        self.assertEqual(ambiguous[101]["anilist"], "9253")
        self.assertEqual(stats["ambiguous_provider_keys"], 1)

    def test_catalog_rejects_cross_anchor_external_id_collisions(self) -> None:
        # The current schema prevents this, but imported/legacy rows must
        # still be rejected if they ever violate the ownership invariant.
        class LegacyConnection:
            def execute(
                self, _query: str, _parameters: object = ()
            ) -> list[tuple[int, str, str]]:
                return [
                    (101, "mal", "5114"),
                    (101, "anilist", "9253"),
                    (202, "mal", "21"),
                    (202, "anilist", "1055"),
                    (303, "mal", "22"),
                    (303, "mal", "5114"),
                ]

            def close(self) -> None:
                pass

        with (
            mock.patch.object(crawl, "mapping_database_metadata"),
            mock.patch.object(
                crawl.sqlite3, "connect", return_value=LegacyConnection()
            ),
        ):
            catalog, stats = crawl.load_catalog(self.mapping)
        self.assertNotIn("mal", catalog[101])
        self.assertEqual(catalog[303], {})
        self.assertEqual(catalog[101]["anilist"], "9253")
        self.assertEqual(stats["ambiguous_external_ids"], 1)
        self.assertEqual(stats["mal_titles"], 1)
        items = crawl.candidates(
            "aniskip", catalog, {}, unknown_episodes=2, max_episodes=48
        )
        self.assertNotIn("5114:1", {item[0] for item in items})

    def test_aniskip_json_and_invalid_segments(self) -> None:
        payload = {
            "found": True,
            "results": [
                {
                    "skipId": "s1",
                    "skipType": "op",
                    "episodeLength": 1440,
                    "interval": {"startTime": 80.125, "endTime": 170.35},
                },
                {
                    "skipId": "bad",
                    "skipType": "ed",
                    "interval": {"startTime": 150, "endTime": 120},
                },
            ],
        }
        rows = crawl.parse_aniskip(payload, "5114", 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["start_ms"], 80125)
        self.assertEqual(rows[0]["end_ms"], 170350)
        self.assertEqual(rows[0]["upstream_lineage"], "aniskip")

    def test_anime_skip_boundary_and_provenance(self) -> None:
        payload = {
            "data": {
                "findShowsByExternalId": [
                    {
                        "id": "show",
                        "episodes": [
                            {
                                "id": "episode",
                                "number": "1",
                                "absoluteNumber": "1",
                                "baseDuration": 1440,
                                "timestamps": [
                                    {
                                        "id": "a",
                                        "at": 0,
                                        "source": "ANIME_SKIP",
                                        "type": {"name": "Intro"},
                                    },
                                    {
                                        "id": "b",
                                        "at": 90,
                                        "source": "ANIME_SKIP",
                                        "type": {"name": "Transition"},
                                    },
                                    {
                                        "id": "c",
                                        "at": 1360,
                                        "source": "ANIME_SKIP",
                                        "type": {"name": "Credits"},
                                    },
                                    {
                                        "id": "d",
                                        "at": 120,
                                        "source": "THIRD_PARTY",
                                        "type": {"name": "Recap"},
                                    },
                                    {
                                        "id": "e",
                                        "at": 180,
                                        "source": "THIRD_PARTY",
                                        "type": {"name": "Transition"},
                                    },
                                ],
                            },
                        ],
                    },
                ]
            }
        }
        rows = crawl.parse_anime_skip(payload, "9253")
        self.assertEqual(len(rows), 5)
        op = next(row for row in rows if row["source_segment_id"] == "a")
        self.assertEqual((op["start_ms"], op["end_ms"]), (0, 90000))
        outro = next(row for row in rows if row["source_segment_id"] == "c")
        self.assertEqual(outro["end_ms"], 1440000)
        third = next(row for row in rows if row["source_segment_id"] == "d")
        self.assertEqual(third["upstream_lineage"], "THIRD_PARTY")
        with self.assertRaises(crawl.BadUpstreamResponse):
            crawl.parse_anime_skip({"errors": [{"message": "oops"}]}, "9253")

    def test_verified_mal_episode_hints_only(self) -> None:
        path = self.root / "timestamps.db"
        create_runtime_database(path)
        with closing(sqlite3.connect(path)) as conn:
            conn.execute(
                "INSERT INTO sources(source_key,display_name) VALUES('aniskip','AniSkip')"
            )
            conn.execute("INSERT INTO titles(anchor_id) VALUES(101)")
            conn.execute(
                "INSERT INTO episodes(anchor_id,episode_key,episode_number) "
                "VALUES(101,'ep:7',7)"
            )
            episode = conn.execute("SELECT id FROM episodes").fetchone()[0]
            conn.execute(
                "INSERT INTO episode_ids(anchor_id,provider,scope,episode_number_text,episode_id) "
                "VALUES(101,'mal','', '7', ?)",
                (episode,),
            )
            conn.commit()
        hints = crawl.mal_episode_hints(path)
        self.assertEqual(hints[101], {7})
        catalog, _ = crawl.load_catalog(self.mapping)
        items = crawl.candidates(
            "aniskip", catalog, hints, unknown_episodes=2, max_episodes=4
        )
        self.assertIn(("5114:7", 101, "5114", 7), items)
        self.assertIn(("21:2", 202, "21", 2), items)

    def test_checkpoint_and_ttl(self) -> None:
        path = self.root / "state" / "aniskip.json.gz"
        crawl.write_gzip_json(path, {"version": 1, "source": "aniskip", "records": {}})
        self.assertEqual(crawl.load_state(path, "aniskip")["records"], {})
        initial = path.read_bytes()
        crawl.write_gzip_json(path, {"records": {}, "source": "aniskip", "version": 1})
        self.assertEqual(path.read_bytes(), initial)
        self.assertEqual(initial[4:8], bytes(4))
        old = (crawl.now() - timedelta(days=16)).isoformat()
        record = {"checked_at": old, "status": "missing", "segments": []}
        self.assertTrue(crawl.due(record, positive_days=30, negative_days=14))
        self.assertFalse(
            crawl.due({**record, "status": "found"}, positive_days=30, negative_days=14)
        )
        with self.assertRaises(ValueError):
            crawl.load_state(path, "anime_skip")

    def test_end_to_end_aniskip_404_and_resume(self) -> None:
        sent = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(str(request.url))
            self.assertEqual(
                request.url.params.get_list("types"), list(crawl.ANISKIP_TYPES)
            )
            if "/5114/" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "found": True,
                        "results": [
                            {
                                "skipId": "one",
                                "skipType": "op",
                                "interval": {"startTime": 2, "endTime": 99},
                            }
                        ],
                    },
                )
            return httpx.Response(404, json={"found": False, "results": []})

        async def run():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                opts = self.options("aniskip", max_requests=3, max_episodes=1)
                first, okay = await crawl.crawl(opts, client=client)
                self.assertTrue(okay)
                self.assertEqual(first["attempted"], 3)
                second, okay = await crawl.crawl(opts, client=client)
                self.assertTrue(okay)
                self.assertEqual(second["attempted"], 0)

        asyncio.run(run())
        self.assertEqual(len(sent), 3)
        with gzip.open(self.root / "out" / "aniskip.jsonl.gz", "rt") as f:
            observations = [json.loads(line) for line in f]
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["anchor_id"], 101)
        self.assertEqual(observations[0]["episode_key"], "ep:1")

    def test_end_to_end_anime_skip_and_api_error(self) -> None:
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            if "9253" in request.content.decode():
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "findShowsByExternalId": [
                                {
                                    "episodes": [
                                        {
                                            "id": "e1",
                                            "number": "1",
                                            "baseDuration": 1000,
                                            "timestamps": [
                                                {
                                                    "id": "t1",
                                                    "at": 20,
                                                    "source": "ANIME_SKIP",
                                                    "type": {"name": "Intro"},
                                                },
                                                {
                                                    "id": "t2",
                                                    "at": 110,
                                                    "source": "ANIME_SKIP",
                                                    "type": {"name": "Transition"},
                                                },
                                            ],
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                )
            return httpx.Response(200, json={"data": {"findShowsByExternalId": []}})

        async def run():
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                report, ok = await crawl.crawl(
                    self.options("anime_skip", max_requests=2), client=client
                )
                self.assertTrue(ok)
                self.assertEqual(report["attempted"], 2)
                self.assertEqual(report["found"], 1)

        asyncio.run(run())
        self.assertEqual(seen[0].headers["X-Client-ID"], "test-only")
        with gzip.open(self.root / "out" / "anime_skip.jsonl.gz", "rt") as f:
            rows = [json.loads(line) for line in f]
        self.assertEqual(rows[0]["upstream_lineage"], "ANIME_SKIP")
        self.assertEqual(rows[0]["anchor_id"], 101)

    def test_anime_skip_missing_backend_row_skips_title_and_resumes(self) -> None:
        sent = []

        def handler(request: httpx.Request) -> httpx.Response:
            external_id = json.loads(request.content)["variables"]["id"]
            sent.append(external_id)
            if external_id == "9253":
                return httpx.Response(
                    200,
                    json={
                        "errors": [
                            {
                                "message": "Row not found in id=00000000-0000-0000-0000-000000000000",
                                "path": [
                                    "findShowsByExternalId",
                                    2,
                                    "episodes",
                                    1,
                                    "timestamps",
                                ],
                            }
                        ],
                        "data": {"findShowsByExternalId": [{"episodes": []}]},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "data": {
                        "findShowsByExternalId": [
                            {
                                "episodes": [
                                    {
                                        "id": "episode",
                                        "number": 1,
                                        "baseDuration": 120,
                                        "timestamps": [
                                            {
                                                "id": "intro",
                                                "at": 10,
                                                "source": "ANIME_SKIP",
                                                "type": {"name": "Intro"},
                                            },
                                            {
                                                "id": "next",
                                                "at": 35,
                                                "source": "ANIME_SKIP",
                                                "type": {"name": "Transition"},
                                            },
                                        ],
                                    }
                                ],
                            }
                        ]
                    }
                },
            )

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                args = self.options("anime_skip", max_requests=2)
                report, ok = await crawl.crawl(args, client=client)
                self.assertTrue(ok)
                self.assertEqual(report["attempted"], 2)
                self.assertEqual(report["skipped_upstream_invalid"], 1)
                self.assertEqual(report["found"], 1)
                self.assertEqual(report["missing"], 0)
                self.assertEqual(report["errors"], [])
                self.assertEqual(report["warnings"][0]["candidate"], "9253")
                second, ok = await crawl.crawl(args, client=client)
                self.assertTrue(ok)
                self.assertEqual(second["attempted"], 0)

        asyncio.run(run())
        self.assertEqual(sent, ["9253", "1055"])
        state = crawl.load_state(
            self.root / "state" / "anime_skip.json.gz", "anime_skip"
        )
        self.assertEqual(state["records"]["9253"]["status"], "source_error")
        self.assertEqual(state["records"]["9253"]["segments"], [])
        self.assertEqual(
            state["records"]["9253"]["last_error_code"], "upstream_broken_reference"
        )
        self.assertFalse(
            crawl.due(state["records"]["9253"], positive_days=30, negative_days=14)
        )
        with gzip.open(self.root / "out" / "anime_skip.jsonl.gz", "rt") as handle:
            rows = [json.loads(line) for line in handle]
        self.assertTrue(rows)
        self.assertTrue(all(row["native_title_id"] == "1055" for row in rows))

    def test_anime_skip_existing_observations_survive_bad_recheck(self) -> None:
        old_segments = [
            {
                "source": "anime_skip",
                "native_title_id": "9253",
                "episode": 1,
                "type": "opening",
                "start_ms": 1000,
                "end_ms": 2000,
                "duration_ms": 120000,
                "source_segment_id": "old",
                "upstream_lineage": "ANIME_SKIP",
            }
        ]
        state_path = self.root / "state" / "anime_skip.json.gz"
        crawl.write_gzip_json(
            state_path,
            {
                "version": 1,
                "source": "anime_skip",
                "records": {
                    "9253": {
                        "status": "found",
                        "checked_at": (crawl.now() - timedelta(days=45)).isoformat(),
                        "segments": old_segments,
                    }
                },
            },
        )

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "errors": [
                        {
                            "message": "Row not found in id=00000000-0000-0000-0000-000000000000",
                        }
                    ]
                },
            )

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                report, ok = await crawl.crawl(
                    self.options("anime_skip", max_requests=1, only_anchor=101),
                    client=client,
                )
                self.assertTrue(ok)
                self.assertEqual(report["skipped_upstream_invalid"], 1)
                self.assertEqual(report["observations"], 1)

        asyncio.run(run())
        record = crawl.load_state(state_path, "anime_skip")["records"]["9253"]
        self.assertEqual(record["status"], "found")
        self.assertEqual(record["segments"], old_segments)
        self.assertFalse(crawl.due(record, positive_days=30, negative_days=14))

    def test_anime_skip_other_graphql_errors_remain_fatal(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"errors": [{"message": "Permission denied"}]}
            )

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                report, ok = await crawl.crawl(
                    self.options("anime_skip", max_requests=2), client=client
                )
                self.assertFalse(ok)
                self.assertEqual(report["attempted"], 0)
                self.assertEqual(report["skipped_upstream_invalid"], 0)
                self.assertEqual(report["errors"][0]["type"], "BadUpstreamResponse")
                self.assertEqual(report["warnings"], [])

        asyncio.run(run())

    def test_aniskip_positive_discovery_expands_episode_frontier(self) -> None:
        episodes = []

        def handler(request: httpx.Request) -> httpx.Response:
            episode = int(request.url.path.split("/")[-1])
            episodes.append(episode)
            return httpx.Response(
                200,
                json={
                    "found": True,
                    "results": [
                        {
                            "skipId": f"skip-{episode}",
                            "skipType": "op",
                            "interval": {"startTime": 10, "endTime": 100},
                        }
                    ],
                },
            )

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                opts = self.options(
                    "aniskip",
                    only_anchor=101,
                    unknown_episodes=1,
                    max_episodes=5,
                    max_requests=1,
                )
                for _ in range(3):
                    report, ok = await crawl.crawl(opts, client=client)
                    self.assertTrue(ok)
                    self.assertEqual(report["attempted"], 1)
                    self.assertGreater(report["initial_unchecked_after_run"], 0)

        asyncio.run(run())
        self.assertEqual(episodes, [1, 2, 3])

    def test_anime_skip_season_number_is_not_assumed_absolute(self) -> None:
        response = {
            "data": {
                "findShowsByExternalId": [
                    {
                        "episodes": [
                            {
                                "id": "ep-season-2",
                                "season": 2,
                                "number": 1,
                                "baseDuration": 1500,
                                "timestamps": [
                                    {
                                        "id": "point",
                                        "at": 1,
                                        "source": "ANIME_SKIP",
                                        "type": {"name": "Intro"},
                                    },
                                    {
                                        "id": "point2",
                                        "at": 80,
                                        "source": "ANIME_SKIP",
                                        "type": {"name": "Transition"},
                                    },
                                ],
                            }
                        ],
                    }
                ]
            }
        }
        result = crawl.parse_anime_skip(response, "9253")
        self.assertEqual(result[0]["episode"], 1)
        self.assertEqual(result[0]["season"], 2)
        self.assertIsNone(result[0]["absolute_number"])
        self.assertFalse(result[0]["episode_identity_proven"])
        self.assertEqual(result[0]["upstream_episode_id"], "ep-season-2")

    def test_checkpoint_export_rejects_inconsistent_records(self) -> None:
        valid = {
            "source": "aniskip",
            "native_title_id": "5114",
            "episode": 1,
            "type": "opening",
            "start_ms": 1000,
            "end_ms": 90000,
            "source_segment_id": "valid",
            "upstream_lineage": "aniskip",
        }
        state = {
            "version": 1,
            "source": "aniskip",
            "records": {
                "5114:1": {
                    "status": "found",
                    "segments": [
                        valid,
                        {**valid, "episode": 2, "source_segment_id": "wrong-ep"},
                        {
                            **valid,
                            "native_title_id": "21",
                            "source_segment_id": "foreign",
                        },
                    ],
                },
                "21:1": {
                    "status": "missing",
                    "segments": [
                        {**valid, "native_title_id": "21", "source_segment_id": "stale"}
                    ],
                },
                "5114:bad": {
                    "status": "found",
                    "segments": [{**valid, "source_segment_id": "bad-key"}],
                },
            },
        }
        catalog, _ = crawl.load_catalog(self.mapping)
        target = self.root / "filtered.jsonl.gz"
        counts = crawl.export_snapshot("aniskip", state, catalog, target)
        self.assertEqual(counts, {"observations": 1, "titles": 1})
        with gzip.open(target, "rt", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        self.assertEqual(rows[0]["source_segment_id"], "valid")
        self.assertEqual(rows[0]["episode_key"], "ep:1")
        self.assertEqual(rows[0]["anchor_id"], 101)

    def test_export_only_has_no_network_effects(self) -> None:
        state = {
            "version": 1,
            "source": "aniskip",
            "records": {
                "5114:1": {
                    "status": "found",
                    "checked_at": crawl.utc_string(),
                    "segments": [
                        {
                            "source": "aniskip",
                            "native_title_id": "5114",
                            "episode": 1,
                            "type": "opening",
                            "start_ms": 0,
                            "end_ms": 1000,
                            "duration_ms": 1500000,
                            "source_segment_id": "id",
                            "upstream_lineage": "aniskip",
                        }
                    ],
                },
            },
        }
        crawl.write_gzip_json(self.root / "state" / "aniskip.json.gz", state)

        def handler(_request: httpx.Request) -> httpx.Response:
            raise AssertionError("No HTTP calls permitted in export-only mode")

        async def run() -> None:
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(handler)
            ) as client:
                opts = self.options("aniskip", export_only=True)
                report, ok = await crawl.crawl(opts, client=client)
                self.assertTrue(ok)
                self.assertEqual(report["attempted"], 0)
                self.assertEqual(report["observations"], 1)

        asyncio.run(run())
        with gzip.open(self.root / "out" / "aniskip.jsonl.gz", "rt") as file:
            row = json.loads(file.readline())
        self.assertEqual(row["anchor_id"], 101)


if __name__ == "__main__":
    unittest.main()
