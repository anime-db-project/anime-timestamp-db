"""Offline fixtures for the two opt-in API crawlers."""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import sqlite3
import tempfile
import unittest
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
        with sqlite3.connect(self.mapping) as conn:
            conn.execute("INSERT INTO nodes VALUES(6, 'mal', '999')")
            conn.execute("INSERT INTO entity_nodes VALUES(1, 6)")
        ambiguous, stats = crawl.load_catalog(self.mapping)
        self.assertNotIn("mal", ambiguous[101])
        self.assertEqual(ambiguous[101]["anilist"], "9253")
        self.assertEqual(stats["ambiguous_provider_keys"], 1)

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
        with sqlite3.connect(path) as conn:
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
                opts = self.options("aniskip", max_requests=3)
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


if __name__ == "__main__":
    unittest.main()
