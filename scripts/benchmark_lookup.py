"""Read-only, warm-cache lookup benchmark for the released timestamp SQLite."""

from __future__ import annotations

import argparse
import json
import platform
import random
import sqlite3
import statistics
import sys
import time
from pathlib import Path

from anime_timestamp_db.resolver import TimestampResolver


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))]


def sample_episodes(path: Path, count: int, seed: int) -> list[tuple[int, str]]:
    with sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True) as db:
        # An indexed existence probe avoids cross multiplying segment rows.
        rows = db.execute("""
            SELECT ep.anchor_id, ep.episode_key
            FROM episodes AS ep
            WHERE EXISTS (SELECT 1 FROM segments s WHERE s.episode_id = ep.id)
              AND EXISTS (SELECT 1 FROM consensus_segments c WHERE c.episode_id = ep.id)
            ORDER BY ep.id
        """).fetchall()
    if not rows:
        raise ValueError("No normalized episodes with consensus and source intervals")
    return random.Random(seed).sample(rows, min(count, len(rows)))


def measure(samples: list[tuple[int, str]], rounds: int, lookup) -> dict[str, object]:
    timings_ms: list[float] = []
    row_counts: list[int] = []
    started = time.perf_counter()
    for _ in range(rounds):
        for anchor, key in samples:
            begin = time.perf_counter_ns()
            results = lookup(f"amdb:{anchor}", key)
            timings_ms.append((time.perf_counter_ns() - begin) / 1_000_000)
            row_counts.append(len(results))
    wall_time = max(time.perf_counter() - started, 1e-9)
    if not any(row_counts):
        raise ValueError("Benchmark queries returned no intervals")
    return {
        "lookups": len(timings_ms),
        "median_ms": round(statistics.median(timings_ms), 4),
        "mean_ms": round(statistics.fmean(timings_ms), 4),
        "p95_ms": round(percentile(timings_ms, 0.95), 4),
        "p99_ms": round(percentile(timings_ms, 0.99), 4),
        "max_ms": round(max(timings_ms), 4),
        "lookups_per_second": round(len(timings_ms) / wall_time, 1),
        "mean_segments": round(statistics.fmean(row_counts), 3),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Benchmark normalized timestamp lookups")
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--samples", type=int, default=250)
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--seed", type=int, default=20261105)
    p.add_argument("--output", type=Path)
    p.add_argument("--build-seconds", type=int)
    a = p.parse_args()
    if a.samples < 1 or a.rounds < 1:
        p.error("--samples and --rounds must be positive")
    db = a.db.resolve()
    samples = sample_episodes(db, a.samples, a.seed)
    resolver = TimestampResolver(db)
    for anchor, key in samples[: min(40, len(samples))]:
        resolver.get_segments_by_anchor(f"amdb:{anchor}", key)
        resolver.get_consensus_by_anchor(f"amdb:{anchor}", key)
    payload = {
        "kind": "timestamp-resolver-warm-sequential-v1",
        "environment": f"{platform.system()} / Python {sys.version_info.major}.{sys.version_info.minor}",
        "cache_mode": "warm",
        "database_bytes": db.stat().st_size,
        "sampled_episodes": len(samples),
        "rounds": a.rounds,
        "build_seconds": a.build_seconds,
        "normalized_lookup": measure(
            samples, a.rounds, resolver.get_segments_by_anchor
        ),
        "consensus_lookup": measure(
            samples, a.rounds, resolver.get_consensus_by_anchor
        ),
    }
    output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
