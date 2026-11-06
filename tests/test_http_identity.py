"""Both crawler implementations use a consistent identifying HTTP header."""

from __future__ import annotations

import unittest

from scripts.http_identity import DEFAULT_CRAWLER_USER_AGENT, crawler_headers


class HTTPIdentityTests(unittest.TestCase):
    def test_default_headers_identify_project_and_request_json(self) -> None:
        headers = crawler_headers()
        self.assertEqual(headers["User-Agent"], DEFAULT_CRAWLER_USER_AGENT)
        self.assertIn(
            "github.com/anime-db-project/anime-timestamp-db", headers["User-Agent"]
        )
        self.assertEqual(headers["Accept"], "application/json")

    def test_explicit_operator_user_agent(self) -> None:
        self.assertEqual(
            crawler_headers("MyProject/2.1 (contact@example.org)")["User-Agent"],
            "MyProject/2.1 (contact@example.org)",
        )
        self.assertEqual(crawler_headers("")["User-Agent"], DEFAULT_CRAWLER_USER_AGENT)

    def test_rejects_control_characters_and_overlong_values(self) -> None:
        for agent in (
            "project\nX-Evil: 1",
            "project\rname",
            "a" * 241,
            "bad\tvalue",
            "агент",
        ):
            with self.subTest(agent=agent[:30]), self.assertRaises(ValueError):
                crawler_headers(agent)


if __name__ == "__main__":
    unittest.main()
