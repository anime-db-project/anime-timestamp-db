from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DESCRIPTOR_RE = re.compile(
    r"^(?P<provider>[A-Za-z_][A-Za-z0-9_]*):(?P<id>[^:]+)(?::(?P<scope>[^:]+))?$"
)
_RANGE_RE = re.compile(r"^(?P<start>[0-9]+)(?:-(?P<end>[0-9]*))?$")


@dataclass(frozen=True, slots=True)
class Descriptor:
    provider: str
    external_id: str
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class EpisodeTarget:
    descriptor: Descriptor
    episode_number: int


@dataclass(frozen=True, slots=True)
class EpisodeMappingResult:
    source_descriptor: str
    targets: tuple[EpisodeTarget, ...]
    skipped_complex_targets: int


@dataclass(frozen=True, slots=True)
class Range:
    start: int
    end: int | None

    def contains(self, value: int) -> bool:
        return value >= self.start and (self.end is None or value <= self.end)

    @property
    def length(self) -> int | None:
        if self.end is None:
            return None
        return self.end - self.start + 1


def parse_descriptor(value: str) -> Descriptor | None:
    match = _DESCRIPTOR_RE.fullmatch(str(value).strip())
    if not match:
        return None
    return Descriptor(
        provider=match.group("provider").casefold(),
        external_id=match.group("id"),
        scope=match.group("scope") or None,
    )


def parse_range(value: str) -> Range | None:
    normalized = str(value).strip()
    match = _RANGE_RE.fullmatch(normalized)
    if not match:
        return None
    start = int(match.group("start"))
    end_raw = match.group("end")
    if "-" not in normalized:
        end = start
    elif end_raw == "":
        end = None
    else:
        end = int(end_raw)
    if end is not None and end < start:
        return None
    return Range(start=start, end=end)


def _parse_target_spec(value: str) -> tuple[tuple[Range, ...], int | None] | None:
    normalized = str(value).strip()
    if not normalized:
        return None
    ratio: int | None = None
    ranges_part = normalized
    if "|" in normalized:
        ranges_part, ratio_raw = normalized.rsplit("|", 1)
        try:
            ratio = int(ratio_raw)
        except ValueError:
            return None
        if ratio == 0:
            return None
    ranges: list[Range] = []
    for raw in ranges_part.split(","):
        parsed = parse_range(raw)
        if parsed is None:
            return None
        ranges.append(parsed)
    return tuple(ranges), ratio


def _target_at_offset(ranges: tuple[Range, ...], offset: int) -> int | None:
    if offset < 0:
        return None
    cursor = offset
    for item in ranges:
        length = item.length
        if length is None:
            return item.start + cursor
        if cursor < length:
            return item.start + cursor
        cursor -= length
    return None


class AniBridgeIndex:
    """Read AniBridge's published mapping payload for safe episode normalization.

    Only one-to-one episode mappings are accepted for timestamp projection. Ratio
    mappings intentionally stay unresolved: a timestamp for a combined/split TV
    episode cannot safely be copied onto a different episode granularity.
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.meta = payload.get("$meta", {}) if isinstance(payload, dict) else {}

    @classmethod
    def from_file(cls, path: Path) -> "AniBridgeIndex":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("AniBridge mapping payload must be a JSON object")
        return cls(payload)

    def resolve_series_episode(
        self,
        imdb_id: str,
        season: int,
        episode: int,
    ) -> EpisodeMappingResult:
        source = f"imdb_show:{imdb_id}:s{season}"
        bucket = self.payload.get(source)
        if not isinstance(bucket, dict):
            return EpisodeMappingResult(source, (), 0)

        targets: list[EpisodeTarget] = []
        skipped_complex = 0
        for target_raw, range_map in bucket.items():
            descriptor = parse_descriptor(target_raw)
            if descriptor is None or descriptor.provider not in {
                "mal",
                "anilist",
                "anidb",
            }:
                continue
            if not isinstance(range_map, dict) or not range_map:
                continue

            mapped_episode: int | None = None
            for source_range_raw, target_spec_raw in range_map.items():
                source_range = parse_range(str(source_range_raw))
                if source_range is None or not source_range.contains(episode):
                    continue
                target_spec = _parse_target_spec(str(target_spec_raw))
                if target_spec is None:
                    continue
                target_ranges, ratio = target_spec
                if ratio is not None:
                    skipped_complex += 1
                    mapped_episode = None
                    break
                offset = episode - source_range.start
                mapped_episode = _target_at_offset(target_ranges, offset)
                break

            if mapped_episode is not None:
                targets.append(EpisodeTarget(descriptor, mapped_episode))

        unique = {
            (
                t.descriptor.provider,
                t.descriptor.external_id,
                t.descriptor.scope,
                t.episode_number,
            ): t
            for t in targets
        }
        ordered = tuple(
            unique[key]
            for key in sorted(
                unique,
                key=lambda item: (
                    {"mal": 0, "anilist": 1, "anidb": 2}.get(item[0], 9),
                    item[1],
                    item[2] or "",
                    item[3],
                ),
            )
        )
        return EpisodeMappingResult(source, ordered, skipped_complex)

    def resolve_movie(self, imdb_id: str) -> tuple[Descriptor, ...]:
        source = f"imdb_movie:{imdb_id}"
        bucket = self.payload.get(source)
        if not isinstance(bucket, dict):
            return ()
        found: dict[tuple[str, str, str | None], Descriptor] = {}
        for target_raw in bucket:
            descriptor = parse_descriptor(target_raw)
            if descriptor is None or descriptor.provider not in {
                "mal",
                "anilist",
                "anidb",
            }:
                continue
            key = (descriptor.provider, descriptor.external_id, descriptor.scope)
            found[key] = descriptor
        return tuple(
            found[key]
            for key in sorted(
                found,
                key=lambda item: (
                    {"mal": 0, "anilist": 1, "anidb": 2}.get(item[0], 9),
                    item[1],
                    item[2] or "",
                ),
            )
        )
