from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from anime_timestamp_db.anibridge import AniBridgeIndex, EpisodeMappingResult
from anime_timestamp_db.config import OPEN_ANIME_TIMESTAMPS
from anime_timestamp_db.database import DatabaseWriter, IdentityConflict


_LINEAGES = {
    "open_anime_timestamps": (
        "open-anime-timestamps",
        "Open Anime Timestamps",
        "Open Anime Timestamps acoustic-fingerprinting observations.",
    ),
    "chapter_data": (
        "open-anime-timestamps-chapter-data",
        "Open Anime Timestamps chapter data",
        "OP/ED ranges inferred by Open Anime Timestamps from media chapter boundaries.",
    ),
    "aniskip": (
        "aniskip",
        "AniSkip",
        "AniSkip timing republished through Open Anime Timestamps.",
    ),
    "anime_skip": (
        "anime-skip",
        "Anime Skip",
        "Anime Skip timing republished through Open Anime Timestamps.",
    ),
    "better_vrv": (
        "better-vrv",
        "BetterVRV",
        "BetterVRV timing republished through Open Anime Timestamps.",
    ),
}
_PROVIDER_PRIORITY = {"mal": 0, "anilist": 1, "anidb": 2}


@dataclass(slots=True)
class OpenAnimeTimestampsStats:
    source: str = OPEN_ANIME_TIMESTAMPS.key
    titles: int = 0
    records: int = 0
    evidence_segments: int = 0
    runtime_segments: int = 0
    source_only_segments: int = 0
    mapped_records: int = 0
    unmapped_records: int = 0
    invalid_records: int = 0
    empty_records: int = 0
    identity_conflicts: int = 0
    single_source_records: int = 0
    aggregate_records: int = 0
    consensus_eligible_segments: int = 0
    consensus_excluded_segments: int = 0
    preview_start_markers: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _episode_text(value: float | None) -> str:
    if value is None:
        return ""
    if value.is_integer():
        return str(int(value))
    return format(value, "g")


def _range(value: object) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    start = _number(value.get("start"))
    end = _number(value.get("end"))
    if start is None or end is None or start < 0 or end <= start:
        return None
    return round(start * 1000), round(end * 1000)


def _lineage(
    writer: DatabaseWriter,
    sources: list[str],
) -> tuple[int, str, bool]:
    normalized = sorted(
        {str(item).strip().casefold() for item in sources if str(item).strip()}
    )
    if len(normalized) == 1:
        source = normalized[0]
        key, name, description = _LINEAGES.get(
            source,
            (
                f"open-anime-timestamps-{source}",
                f"Open Anime Timestamps: {source}",
                "Single upstream lineage reported by Open Anime Timestamps.",
            ),
        )
        return writer.lineage_id(key, name, description), key, True

    key = "open-anime-timestamps-aggregate"
    description = (
        "Open Anime Timestamps record assembled from multiple upstream sources. "
        "Field-level provenance is unavailable, so these observations are excluded "
        "from consensus voting while remaining queryable."
    )
    return (
        writer.lineage_id(key, "Open Anime Timestamps aggregate", description),
        key,
        False,
    )


def _anchor(result: EpisodeMappingResult) -> tuple[str, str, int] | None:
    by_provider: dict[str, set[tuple[str, int]]] = {}
    for target in result.targets:
        by_provider.setdefault(target.descriptor.provider, set()).add(
            (target.descriptor.external_id, target.episode_number)
        )
    for provider in sorted(
        by_provider, key=lambda item: _PROVIDER_PRIORITY.get(item, 99)
    ):
        values = by_provider[provider]
        if len(values) == 1:
            external_id, episode = next(iter(values))
            return provider, external_id, episode
    return None


def _attach_target_ids(
    writer: DatabaseWriter,
    *,
    title_id: int,
    episode_id: int,
    anchor_provider: str,
    anchor_id: str,
    source_anidb_id: str,
    source_episode: int,
    result: EpisodeMappingResult,
) -> None:
    aliases: list[tuple[str, str]] = [("anidb", source_anidb_id)]
    aliases.extend(
        (target.descriptor.provider, target.descriptor.external_id)
        for target in result.targets
    )
    for provider, external_id in aliases:
        try:
            resolved = writer.get_or_create_title(
                {anchor_provider: anchor_id, provider: external_id}
            )
        except IdentityConflict:
            continue
        if resolved != title_id:
            continue

    try:
        writer.add_episode_id(
            episode_id=episode_id,
            provider="anidb",
            title_external_id=source_anidb_id,
            scope="R",
            episode_number=source_episode,
        )
    except IdentityConflict:
        pass

    for target in result.targets:
        belongs = writer.conn.execute(
            "SELECT title_id FROM title_ids WHERE provider=? AND external_id=?",
            (target.descriptor.provider, target.descriptor.external_id),
        ).fetchone()
        if belongs is None or int(belongs[0]) != title_id:
            continue
        try:
            writer.add_episode_id(
                episode_id=episode_id,
                provider=target.descriptor.provider,
                title_external_id=target.descriptor.external_id,
                scope=target.descriptor.scope or "",
                episode_number=target.episode_number,
            )
        except IdentityConflict:
            continue


def import_open_anime_timestamps(
    path: Path,
    *,
    writer: DatabaseWriter,
    snapshot_id: int,
    anibridge: AniBridgeIndex,
) -> OpenAnimeTimestampsStats:
    stats = OpenAnimeTimestampsStats()
    source_id = writer.source_id(OPEN_ANIME_TIMESTAMPS)

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Open Anime Timestamps database must be a JSON object")

    stats.titles = len(payload)
    for anidb_id, rows in payload.items():
        if not isinstance(rows, list):
            stats.invalid_records += 1
            continue
        source_title_key = str(anidb_id).strip()
        for row_index, raw in enumerate(rows):
            stats.records += 1
            if not isinstance(raw, dict) or not source_title_key:
                stats.invalid_records += 1
                continue

            digest = _canonical_hash(raw)
            episode_number = _number(raw.get("episode_number"))
            episode_text = _episode_text(episode_number)
            source_episode_key = (
                f"R:{episode_text}" if episode_text else f"row:{row_index}"
            )
            upstream_sources = (
                raw.get("sources") if isinstance(raw.get("sources"), list) else []
            )
            lineage_id, lineage_key, consensus_eligible = _lineage(
                writer, upstream_sources
            )
            if consensus_eligible:
                stats.single_source_records += 1
            else:
                stats.aggregate_records += 1

            ranges = {
                segment_type: parsed
                for segment_type, parsed in (
                    ("recap", _range(raw.get("recap"))),
                    ("opening", _range(raw.get("opening"))),
                    ("ending", _range(raw.get("ending"))),
                )
                if parsed is not None
            }
            preview_start = _number(raw.get("preview_start"))
            if preview_start is not None and preview_start >= 0:
                stats.preview_start_markers += 1

            result: EpisodeMappingResult | None = None
            anchor: tuple[str, str, int] | None = None
            source_episode: int | None = None
            if (
                episode_number is not None
                and episode_number > 0
                and episode_number.is_integer()
            ):
                source_episode = int(episode_number)
                result = anibridge.resolve_anidb_episode(
                    source_title_key,
                    source_episode,
                    scope="R",
                )
                anchor = _anchor(result)

            runtime_episode_id: int | None = None
            normalization_status = "source-only"
            normalization_reason = "AniDB regular-episode bridge unresolved"
            normalized_provider = ""
            normalized_id = ""
            normalized_episode_key = ""

            if not ranges:
                normalization_status = "empty"
                normalization_reason = (
                    "preview-only point marker preserved in evidence metadata"
                    if preview_start is not None and preview_start >= 0
                    else "no ranged timestamp fields"
                )
                stats.empty_records += 1
            elif anchor is not None and source_episode is not None:
                anchor_provider, anchor_id, target_episode = anchor
                normalized_provider = anchor_provider
                normalized_id = anchor_id
                normalized_episode_key = f"ep:{target_episode}"
                try:
                    title_id = writer.get_or_create_title({anchor_provider: anchor_id})
                    runtime_episode_id = writer.get_or_create_episode(
                        title_id,
                        episode_key=normalized_episode_key,
                        episode_number=target_episode,
                    )
                    writer.add_episode_ref(
                        source_id,
                        source_title_key=source_title_key,
                        source_episode_key=source_episode_key,
                        episode_id=runtime_episode_id,
                        source_episode_number_text=episode_text,
                    )
                    _attach_target_ids(
                        writer,
                        title_id=title_id,
                        episode_id=runtime_episode_id,
                        anchor_provider=anchor_provider,
                        anchor_id=anchor_id,
                        source_anidb_id=source_title_key,
                        source_episode=source_episode,
                        result=result,
                    )
                    normalization_status = "mapped"
                    normalization_reason = "exact-anidb-r-anibridge"
                    stats.mapped_records += 1
                except IdentityConflict as exc:
                    runtime_episode_id = None
                    normalization_status = "source-only"
                    normalization_reason = f"identity conflict: {exc}"
                    stats.identity_conflicts += 1
            else:
                stats.unmapped_records += 1

            record_key = (
                f"oat:{source_title_key}:{episode_text or row_index}:{digest[:16]}"
            )
            metadata = {
                "upstream_sources": sorted({str(item) for item in upstream_sources}),
                "field_level_lineage_available": len(set(upstream_sources)) == 1,
                "consensus_eligible": consensus_eligible,
                "preview_start_seconds": preview_start
                if preview_start is not None and preview_start >= 0
                else None,
                "anibridge_source": result.source_descriptor
                if result is not None
                else "",
                "anibridge_targets": [
                    {
                        "provider": target.descriptor.provider,
                        "id": target.descriptor.external_id,
                        "scope": target.descriptor.scope or "",
                        "episode": target.episode_number,
                    }
                    for target in (result.targets if result is not None else ())
                ],
            }
            record_id = writer.add_evidence_record(
                snapshot_id=snapshot_id,
                record_key=record_key,
                lineage_key=lineage_key,
                source_title_key=source_title_key,
                source_episode_key=source_episode_key,
                payload_sha256=digest,
                normalization_status=normalization_status,
                normalization_reason=normalization_reason,
                normalized_provider=normalized_provider,
                normalized_id=normalized_id,
                normalized_episode_key=normalized_episode_key,
                metadata=metadata,
            )

            for segment_type, (start_ms, end_ms) in ranges.items():
                segment_id = f"{record_key}:{segment_type}"
                writer.add_evidence_segment(
                    record_id,
                    source_segment_id=segment_id,
                    segment_type=segment_type,
                    start_ms=start_ms,
                    end_ms=end_ms,
                )
                stats.evidence_segments += 1
                if runtime_episode_id is not None:
                    writer.add_segment(
                        episode_id=runtime_episode_id,
                        source_id=source_id,
                        lineage_id=lineage_id,
                        source_segment_id=segment_id,
                        segment_type=segment_type,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        mapping_method="exact-anidb-r-anibridge",
                        mapping_confidence=1.0,
                        consensus_eligible=consensus_eligible,
                    )
                    stats.runtime_segments += 1
                    if consensus_eligible:
                        stats.consensus_eligible_segments += 1
                    else:
                        stats.consensus_excluded_segments += 1
                else:
                    writer.add_source_segment(
                        source_id=source_id,
                        lineage_id=lineage_id,
                        source_title_key=source_title_key,
                        source_episode_key=source_episode_key,
                        source_segment_id=segment_id,
                        segment_type=segment_type,
                        start_ms=start_ms,
                        end_ms=end_ms,
                    )
                    stats.source_only_segments += 1

            if stats.records % 5000 == 0:
                writer.commit()

    writer.set_snapshot_record_count(snapshot_id, stats.records)
    writer.commit()
    return stats
