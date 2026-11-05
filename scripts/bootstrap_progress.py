"""Validate both source reports and decide whether bootstrap needs another batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def bootstrap_plan(root: Path, remaining_runs: int) -> dict[str, object]:
    if not 1 <= remaining_runs <= 160:
        raise ValueError("remaining_runs must be an integer between 1 and 160")
    incomplete: dict[str, int] = {}
    for source in ("aniskip", "anime_skip"):
        # GitHub upload-artifact can flatten a common root depending on the
        # files uploaded. Accept exactly one matching report at any depth.
        matches = list((root / source).rglob(f"{source}-report.json"))
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one {source} report, found {len(matches)}"
            )
        report = json.loads(matches[0].read_text("utf-8"))
        if not isinstance(report, dict) or report.get("source") != source:
            raise ValueError(f"Invalid source identity in {matches[0]}")
        if report.get("errors"):
            raise ValueError(f"Fatal {source} crawler error: {report['errors']}")
        if report.get("stopped_reason") == "rate_limited_after_retry":
            # Partial checkpoint has been persisted. Do not re-dispatch a
            # bootstrap job that will hit the same provider limit.
            return {
                "continue": "false",
                "next_runs": remaining_runs - 1,
                "rate_limited_source": source,
            }
        pending = report.get("initial_unchecked_after_run")
        if isinstance(pending, bool) or not isinstance(pending, int) or pending < 0:
            raise ValueError(f"Invalid initial_unchecked_after_run for {source}")
        completed = report.get("attempted")
        if isinstance(completed, bool) or not isinstance(completed, int):
            raise ValueError(f"Invalid attempted count for {source}")
        # Never chain endlessly if source progress stalls due to bad state.
        if pending and completed <= 0:
            raise ValueError(f"{source} bootstrap stalled with {pending} unseen")
        incomplete[source] = pending

    continue_run = any(incomplete.values()) and remaining_runs > 1
    return {
        "continue": "true" if continue_run else "false",
        "next_runs": remaining_runs - 1,
        "unseen_aniskip": incomplete["aniskip"],
        "unseen_anime_skip": incomplete["anime_skip"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--remaining-runs", type=int, required=True)
    args = parser.parse_args()
    plan = bootstrap_plan(args.root, args.remaining_runs)
    for key, value in plan.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
