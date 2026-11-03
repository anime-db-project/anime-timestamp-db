"""Prepare API checkpoints for all-or-nothing automatic release imports.

An uninitialized checkpoint branch is normal while crawling begins. An
existing but invalid checkpoint is fatal, not a reason to discard data.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from scripts.checkpoint_store import restore

SOURCES = ("aniskip", "anime_skip")


def prepare_api_import(output_dir: Path) -> dict[str, object]:
    """Enable API imports only after both source checkpoints were restored."""
    status: dict[str, str] = {}
    for source in SOURCES:
        target = output_dir / f"{source}.json.gz"
        # Never mistake a local stale file for the current remote checkpoint.
        target.unlink(missing_ok=True)
        result = restore(source, target)
        if result["restored"]:
            if not target.is_file() or target.stat().st_size == 0:
                raise RuntimeError(
                    f"{source} claimed restored but checkpoint is absent"
                )
            status[source] = "ready"
        else:
            status[source] = "pending"
    return {
        "enabled": all(value == "ready" for value in status.values()),
        "sources": status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("api-checkpoints"))
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    result = prepare_api_import(args.output_dir)

    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"enabled={str(result['enabled']).lower()}\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("### Live API import\n")
            for source, state in result["sources"].items():
                handle.write(f"- {source}: {state}\n")
            handle.write(
                "- Import both sources: "
                + ("enabled" if result["enabled"] else "waiting for checkpoints")
                + "\n"
            )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
