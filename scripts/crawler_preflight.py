"""GitHub Actions source preflight driven by the same config as the crawler.

A completed job is not evidence that requests were made. Explicitly report
disabled sources, and fail visibly when a required credential is missing.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from scripts.source_policies import SourcePolicy, load_policies


@dataclass(frozen=True)
class PreflightDecision:
    enabled: bool
    fatal: bool = False
    reason: str = ""


def decide(
    source: str,
    *,
    mode: str = "maintenance",
    env: Mapping[str, str] | None = None,
    policies: Mapping[str, SourcePolicy] | None = None,
) -> PreflightDecision:
    if mode not in ("maintenance", "bootstrap"):
        raise ValueError("Invalid crawler mode")
    policy = (policies or load_policies())[source]
    environ = os.environ if env is None else env

    if not policy.enabled:
        return PreflightDecision(
            False,
            reason=f"{source}: automatic crawling disabled in "
            "config/crawler_sources.json (enabled=false)",
        )

    # A repository maintainer sets this config after confirming permission.
    # It is not possible to obtain permission by adding a source credit.
    if policy.requires_bulk_permission:
        return PreflightDecision(
            False,
            reason=f"{source}: requires upstream bulk-collection permission; "
            "the source is disabled in config/crawler_sources.json",
        )
    if source == "publicmetadb" and not environ.get("PUBLICMETADB_API_KEY", "").strip():
        return PreflightDecision(
            False,
            fatal=True,
            reason="PublicMetaDB is enabled but repository Actions secret "
            "PUBLICMETADB_API_KEY is missing",
        )
    if source == "anime_skip" and not environ.get("ANIME_SKIP_CLIENT_ID", "").strip():
        return PreflightDecision(
            False,
            fatal=mode == "bootstrap",
            reason="Anime Skip requires Actions secret ANIME_SKIP_CLIENT_ID",
        )
    return PreflightDecision(True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=tuple(load_policies()), required=True)
    parser.add_argument(
        "--mode", choices=("maintenance", "bootstrap"), default="maintenance"
    )
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--github-summary", type=Path)
    args = parser.parse_args(argv)
    decision = decide(args.source, mode=args.mode)

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"enabled={'true' if decision.enabled else 'false'}\n")
    if args.github_summary:
        with args.github_summary.open("a", encoding="utf-8") as summary:
            summary.write(
                f"- **{args.source}**: "
                + ("ready to crawl" if decision.enabled else decision.reason)
                + "\n"
            )
    if decision.reason:
        severity = "error" if decision.fatal else "warning"
        print(f"::{severity}::{decision.reason}")
    else:
        print(f"{args.source}: crawler enabled by source configuration")
    return 2 if decision.fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
