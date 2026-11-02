from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    manifest = json.loads(Path(sys.argv[1]).read_text("utf-8"))
    runtime = manifest["audit"]["runtime"]
    evidence = manifest["audit"]["evidence"]
    print("# Anime Timestamp DB build")
    print()
    print(f"- Schema: `{manifest['schema_version']}`")
    print(f"- Audit: `{'PASS' if manifest['audit']['ok'] else 'FAIL'}`")
    print(f"- Normalized segments: **{runtime['counts']['segments']:,}**")
    print(f"- Source-only segments: **{runtime['counts']['source_segments']:,}**")
    print(f"- Consensus segments: **{runtime['counts']['consensus_segments']:,}**")
    print(f"- Normalized titles: **{runtime['counts']['titles']:,}**")
    print(f"- Normalized episodes: **{runtime['counts']['episodes']:,}**")
    print(f"- Evidence records: **{evidence['counts']['records']:,}**")
    print()
    print("## Import results")
    for name, stats in manifest["imports"].items():
        if isinstance(stats, dict):
            print(f"- **{name}**: `{json.dumps(stats, sort_keys=True)}`")
        else:
            print(f"- **{name}**: {stats:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
