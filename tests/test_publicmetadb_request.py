"""Regression for the PublicMetaDB API media-type query parameter."""

from __future__ import annotations

import unittest

from scripts.external_sources import make_request


class PublicMetaDBRequestTests(unittest.TestCase):
    def test_tv_request_has_required_media_type_and_auth(self) -> None:
        url, headers, params = make_request(
            "publicmetadb", "tmdb_tv", "26340", 1, 1, api_key="test-key"
        )
        self.assertEqual(url, "https://publicmetadb.com/api/external/skips")
        self.assertEqual(
            params,
            {
                "season": 1,
                "episode": 1,
                "tmdb_id": "26340",
                "media_type": "tv",
            },
        )
        self.assertEqual(headers["Authorization"], "Bearer test-key")

    def test_key_still_required(self) -> None:
        with self.assertRaises(ValueError):
            make_request("publicmetadb", "tmdb_tv", "26340", 1, 1)


if __name__ == "__main__":
    unittest.main()
