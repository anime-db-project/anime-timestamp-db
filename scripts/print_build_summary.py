from __future__ import annotations

import json
import sys
from pathlib import Path


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def main() -> int:
    manifest = json.loads(Path(sys.argv[1]).read_text("utf-8"))
    runtime = manifest["audit"]["runtime"]
    evidence = manifest["audit"]["evidence"]
    identity = manifest.get("identity", {})

    print("# Anime Timestamp DB build")
    print()
    print(f"- Schema: `{manifest['schema_version']}`")
    print(f"- Build format: `{manifest['build_format_version']}`")
    print(f"- Audit: `{'PASS' if manifest['audit']['ok'] else 'FAIL'}`")
    print(f"- Identity namespace: `{identity.get('namespace', 'amdb')}`")
    print(f"- Normalized segments: **{runtime['counts']['segments']:,}**")
    print(f"- Source-only segments: **{runtime['counts']['source_segments']:,}**")
    print(f"- Consensus segments: **{runtime['counts']['consensus_segments']:,}**")
    print(f"- AMDB titles: **{runtime['counts']['titles']:,}**")
    print(f"- Normalized episodes: **{runtime['counts']['episodes']:,}**")
    print(f"- Provider episode IDs: **{runtime['counts']['episode_ids']:,}**")
    print(f"- Evidence records: **{evidence['counts']['records']:,}**")

    print()
    print("## Import results")
    for name, stats in manifest["imports"].items():
        if isinstance(stats, dict):
            print(f"- **{name}**: `{_compact(stats)}`")
        else:
            print(f"- **{name}**: {stats:,}")

    for title, key in (
        ("Identity", "identity"),
        ("Normalization", "normalization"),
        ("Episode index", "episode_index"),
        ("Consensus", "consensus"),
    ):
        if key in manifest:
            print()
            print(f"## {title}")
            print(f"`{_compact(manifest[key])}`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
