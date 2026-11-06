"""Preflight regression tests: repository configuration, not hardcoded Actions variables."""

from __future__ import annotations

import unittest
from dataclasses import replace

from scripts.crawler_preflight import decide
from scripts.source_policies import load_policies


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policies = load_policies()

    def test_config_decides_whether_intro_providers_run(self) -> None:
        for source in ("introdb", "introhater", "theintrodb"):
            with self.subTest(source=source):
                enabled = {
                    **self.policies,
                    source: replace(
                        self.policies[source],
                        requires_bulk_permission=False,
                        enabled=True,
                    ),
                }
                blocked = {
                    **self.policies,
                    source: replace(
                        self.policies[source],
                        requires_bulk_permission=True,
                        enabled=True,
                    ),
                }
                self.assertTrue(decide(source, env={}, policies=enabled).enabled)
                result = decide(source, env={}, policies=blocked)
                self.assertFalse(result.enabled)
                self.assertFalse(result.fatal)
                self.assertIn("requires upstream", result.reason)

    def test_theintrodb_is_disabled_without_being_deleted(self) -> None:
        policy = self.policies["theintrodb"]
        self.assertFalse(policy.enabled)
        disabled = decide("theintrodb", env={}, policies=self.policies)
        self.assertFalse(disabled.enabled)
        self.assertFalse(disabled.fatal)
        self.assertIn("enabled=false", disabled.reason)
        enabled = {
            **self.policies,
            "theintrodb": replace(policy, enabled=True),
        }
        self.assertTrue(decide("theintrodb", env={}, policies=enabled).enabled)

    def test_publicmetadb_needs_real_secret_not_obsolete_approval_variable(
        self,
    ) -> None:
        policies = {
            **self.policies,
            "publicmetadb": replace(
                self.policies["publicmetadb"], requires_bulk_permission=False
            ),
        }
        missing = decide("publicmetadb", env={}, policies=policies)
        self.assertFalse(missing.enabled)
        self.assertTrue(missing.fatal)
        self.assertIn("PUBLICMETADB_API_KEY", missing.reason)
        ready = decide(
            "publicmetadb",
            env={"PUBLICMETADB_API_KEY": "fixture-key"},
            policies=policies,
        )
        self.assertTrue(ready.enabled)
        self.assertFalse(ready.fatal)

    def test_anime_skip_client_id_and_other_sources(self) -> None:
        missing = decide("anime_skip", env={}, policies=self.policies)
        self.assertFalse(missing.enabled)
        self.assertFalse(missing.fatal)
        bootstrap = decide(
            "anime_skip", mode="bootstrap", env={}, policies=self.policies
        )
        self.assertTrue(bootstrap.fatal)
        ready = decide(
            "anime_skip",
            env={"ANIME_SKIP_CLIENT_ID": "fixture-id"},
            policies=self.policies,
        )
        self.assertTrue(ready.enabled)
        self.assertTrue(decide("aniskip", env={}, policies=self.policies).enabled)


if __name__ == "__main__":
    unittest.main()
