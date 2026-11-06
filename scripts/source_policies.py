"""Per-provider, auditable request budgets and polite sliding-window pacing.

Delays deliberately smooth load on upstreams; they are not anti-bot evasion.
Unknown public limits are NOT inferred from third-party client configuration.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

SOURCE_CONFIG = Path(__file__).resolve().parents[1] / "config" / "crawler_sources.json"


@dataclass(frozen=True)
class SourcePolicy:
    source: str
    max_requests: int
    per_second: int
    per_minute: int
    per_hour: int
    delay_seconds: tuple[float, float]
    retry_429_wait_seconds: int
    max_429_wait_seconds: int
    requires_bulk_permission: bool
    enabled: bool = True

    @classmethod
    def from_row(cls, source: str, row: dict) -> SourcePolicy:
        lo, hi = row["delay_seconds"]
        enabled = row.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"{source}: enabled must be a boolean")
        result = cls(
            source=source,
            max_requests=int(row["max_requests"]),
            per_second=int(row["per_second"]),
            per_minute=int(row["per_minute"]),
            per_hour=int(row["per_hour"]),
            delay_seconds=(float(lo), float(hi)),
            retry_429_wait_seconds=int(row["retry_429_wait_seconds"]),
            max_429_wait_seconds=int(row["max_429_wait_seconds"]),
            requires_bulk_permission=bool(row["requires_bulk_permission"]),
            enabled=enabled,
        )
        if not (1 <= result.max_requests <= 5000):
            raise ValueError(f"{source}: invalid per-run request budget")
        if any(n < 1 for n in (result.per_second, result.per_minute, result.per_hour)):
            raise ValueError(f"{source}: rate windows must be positive")
        if not (0 <= lo <= hi <= 10):
            raise ValueError(f"{source}: delay interval must be [0,10] seconds")
        if not (
            0 <= result.retry_429_wait_seconds <= result.max_429_wait_seconds <= 600
        ):
            raise ValueError(f"{source}: invalid 429 retry policy")
        return result


def load_policies(path: Path = SOURCE_CONFIG) -> dict[str, SourcePolicy]:
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("crawler configuration must be a JSON object")
    result = {source: SourcePolicy.from_row(source, row) for source, row in raw.items()}
    required = {
        "aniskip",
        "anime_skip",
        "introdb",
        "publicmetadb",
        "theintrodb",
        "introhater",
    }
    if set(result) != required:
        raise ValueError(f"crawler policies must contain exactly {sorted(required)}")
    return result


class PacedLimiter:
    """One caller, three sliding windows, independent of HTTP method and retries."""

    def __init__(self, policy: SourcePolicy, *, jitter: bool = True) -> None:
        self.policy = policy
        self.jitter = jitter
        self._windows = [
            (1.0, policy.per_second, deque()),
            (60.0, policy.per_minute, deque()),
            (3600.0, policy.per_hour, deque()),
        ]
        self._previous: float | None = None

    async def wait(self) -> None:
        if self._previous is not None and self.jitter:
            gap = random.uniform(*self.policy.delay_seconds)
            until = self._previous + gap
            if until > time.monotonic():
                await asyncio.sleep(until - time.monotonic())
        while True:
            current = time.monotonic()
            waiting = 0.0
            for interval, count, seen in self._windows:
                while seen and current - seen[0] >= interval:
                    seen.popleft()
                if len(seen) >= count:
                    waiting = max(waiting, seen[0] + interval - current)
            if waiting <= 0:
                break
            await asyncio.sleep(waiting + 0.01)
        current = time.monotonic()
        for _interval, _count, seen in self._windows:
            seen.append(current)
        self._previous = current
