from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from anime_timestamp_db.config import BAHA, SKIPDB
from anime_timestamp_db.database import DatabaseWriter, IdentityConflict
from anime_timestamp_db.mapping_identity import (
    AnchorResolutionConflict,
    MappingAnchorIndex,
)
from anime_timestamp_db.skipdb_mapping import EpisodeResolution, SkipDBMappingIndex

_SKIPDB_TYPES = {
    "intro": "opening",
    "recap": "recap",
    "outro": "ending",
    "preview": "preview",
}
_BAHA_TYPES = {
    "OP": "opening",
    "ED": "ending",
}


@dataclass(slots=True)
class ImportStats:
    source: str
    records: int = 0
    evidence_segments: int = 0
    runtime_segments: int = 0
    source_only_segments: int = 0
    approved: int = 0
    pending: int = 0
    rejected: int = 0
    mapped: int = 0
    unmapped: int = 0
    ambiguous: int = 0
    invalid: int = 0
    skipped_status: int = 0
    skipped_complex_mappings: int = 0
    anime_titles_detected: int = 0
    exact_episode_mappings: int = 0
    inferred_episode_mappings: int = 0
    runtime_segments_exact: int = 0
    runtime_segments_inferred: int = 0
    anime_source_only_segments: int = 0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _payload_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _safe_int(value: object, *, minimum: int | None = None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None and parsed < minimum:
        return None
    return parsed


def _safe_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolution_metadata(resolution: EpisodeResolution | None) -> dict[str, object]:
    if resolution is None:
        return {}
    return {
        "mapping_method": resolution.method,
        "mapping_confidence": resolution.confidence,
        "mapping_routes": list(resolution.routes),
        "target_episode": resolution.episode_number,
        "target_provider_count": len(resolution.ids),
    }


def import_skipdb(
    path: Path,
    *,
    writer: DatabaseWriter,
    snapshot_id: int,
    mappings: SkipDBMappingIndex,
    identities: MappingAnchorIndex,
) -> ImportStats:
    stats = ImportStats(source=SKIPDB.key)
    source_id = writer.source_id(SKIPDB)
    lineage_id = writer.lineage_id(
        "skipdb",
        "SkipDB",
        "Independent crowdsourced SkipDB timing observations.",
    )

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("segments", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        raise ValueError("SkipDB dump must contain a 'segments' array")

    valid_rows = [raw for raw in rows if isinstance(raw, dict)]
    episode_map, plan_stats = mappings.prepare_series_episode_map(valid_rows)
    direct_anime_imdb_ids = {
        str(raw.get("imdb_id") or "").strip()
        for raw in valid_rows
        if str(raw.get("imdb_id") or "").strip()
        and mappings.title_candidates(str(raw.get("imdb_id") or "").strip()).is_anime
    }
    bridge_anime_imdb_ids = {imdb_id for imdb_id, _season, _episode in episode_map}
    anime_imdb_ids = direct_anime_imdb_ids | bridge_anime_imdb_ids
    stats.anime_titles_detected = len(anime_imdb_ids)
    stats.exact_episode_mappings = plan_stats.exact_episodes
    stats.inferred_episode_mappings = plan_stats.inferred_episodes
    movie_cache: dict[str, EpisodeResolution | None] = {}

    for index, raw in enumerate(rows):
        stats.records += 1
        if not isinstance(raw, dict):
            stats.invalid += 1
            continue

        digest = _payload_hash(raw)
        record_key = f"skipdb:{digest}"
        source_segment_id = record_key
        imdb_id = str(raw.get("imdb_id") or "").strip()
        media_type = str(raw.get("media_type") or "").strip().casefold()
        status = str(raw.get("status") or "").strip().casefold()
        segment_type = _SKIPDB_TYPES.get(str(raw.get("segment_type") or "").casefold())
        start_ms = _safe_int(raw.get("start_ms"), minimum=0)
        end_ms = _safe_int(raw.get("end_ms"), minimum=1)
        media_duration_ms = _safe_int(raw.get("duration_ms"), minimum=1)
        votes_up = _safe_int(raw.get("votes_up"), minimum=0) or 0
        votes_down = _safe_int(raw.get("votes_down"), minimum=0) or 0
        quality_score = _safe_float(raw.get("score"))
        season = _safe_int(raw.get("season"), minimum=0)
        episode = _safe_int(raw.get("episode"), minimum=0)
        display_title = str(raw.get("title") or "").strip()

        if status == "approved":
            stats.approved += 1
        elif status == "pending":
            stats.pending += 1
        elif status == "rejected":
            stats.rejected += 1

        source_title_key = imdb_id
        source_episode_key = ""
        if media_type == "series" and season is not None and episode is not None:
            source_title_key = f"{imdb_id}:s{season}"
            source_episode_key = f"e{episode}"
        elif media_type == "movie":
            source_episode_key = "movie"

        valid_range = (
            bool(imdb_id)
            and segment_type is not None
            and start_ms is not None
            and end_ms is not None
            and end_ms > start_ms
        )
        title_candidates = mappings.title_candidates(imdb_id) if imdb_id else None
        resolution: EpisodeResolution | None = None
        if (
            valid_range
            and media_type == "series"
            and season is not None
            and episode is not None
        ):
            resolution = episode_map.get((imdb_id, season, episode))
        elif valid_range and media_type == "movie":
            if imdb_id not in movie_cache:
                movie_cache[imdb_id] = mappings.resolve_movie(imdb_id)
            resolution = movie_cache[imdb_id]
            if resolution is not None:
                anime_imdb_ids.add(imdb_id)

        normalization_status = "unprocessed"
        normalization_reason = ""
        normalized_anchor_id: int | None = None
        normalized_episode_key = ""
        runtime_episode_id: int | None = None

        if not valid_range:
            normalization_status = "invalid"
            normalization_reason = "missing identifier/type or invalid timestamp range"
            stats.invalid += 1
        elif resolution is not None:
            try:
                normalized_anchor_id = identities.anchor_for_ids(resolution.ids)
            except AnchorResolutionConflict as exc:
                normalization_status = "ambiguous"
                normalization_reason = str(exc)
                stats.ambiguous += 1
            else:
                if normalized_anchor_id is None:
                    normalization_status = "source-only"
                    normalization_reason = "resolved episode has no AMDB title anchor"
                    stats.unmapped += 1
                else:
                    normalization_status = (
                        "mapped-inferred"
                        if resolution.method == "inferred-season-offset"
                        else "mapped"
                    )
                    normalization_reason = resolution.method
                    normalized_episode_key = resolution.episode_key
                    stats.mapped += 1

                    if status == "approved":
                        try:
                            writer.get_or_create_title(
                                normalized_anchor_id,
                                display_title=display_title,
                            )
                            runtime_episode_id = writer.get_or_create_episode(
                                normalized_anchor_id,
                                episode_key=resolution.episode_key,
                                episode_number=resolution.episode_number,
                                is_special=resolution.is_special,
                            )
                            writer.add_episode_ref(
                                source_id,
                                source_title_key=source_title_key,
                                source_episode_key=source_episode_key,
                                episode_id=runtime_episode_id,
                                source_episode_number_text=(
                                    "" if episode is None else str(episode)
                                ),
                            )
                            for target in resolution.provider_episodes:
                                if (
                                    identities.anchor_for(
                                        target.descriptor.provider,
                                        target.descriptor.external_id,
                                    )
                                    != normalized_anchor_id
                                ):
                                    continue
                                try:
                                    writer.add_episode_id(
                                        episode_id=runtime_episode_id,
                                        anchor_id=normalized_anchor_id,
                                        provider=target.descriptor.provider,
                                        scope=target.descriptor.scope or "",
                                        episode_number=target.episode_number,
                                    )
                                except IdentityConflict:
                                    continue
                        except IdentityConflict as exc:
                            normalization_status = "ambiguous"
                            normalization_reason = str(exc)
                            normalized_anchor_id = None
                            normalized_episode_key = ""
                            runtime_episode_id = None
                            stats.ambiguous += 1
        elif imdb_id in anime_imdb_ids:
            normalization_status = "source-only"
            normalization_reason = (
                "anime title identified but episode mapping is unresolved"
            )
            stats.unmapped += 1
        else:
            normalization_status = "unmapped"
            normalization_reason = "no anime identity in mappings.db"
            stats.unmapped += 1

        candidate_counts = (
            {
                "mal": len(title_candidates.mal),
                "anilist": len(title_candidates.anilist),
                "anidb": len(title_candidates.anidb),
            }
            if title_candidates is not None
            else {}
        )
        metadata = {
            "media_type": media_type,
            "season": season,
            "episode": episode,
            "title": display_title,
            "created_at": str(raw.get("created_at") or ""),
            "anime_candidate_counts": candidate_counts,
            "anime_detected_by_episode_bridge": imdb_id in bridge_anime_imdb_ids,
            **_resolution_metadata(resolution),
        }
        record_id = writer.add_evidence_record(
            snapshot_id=snapshot_id,
            record_key=record_key,
            lineage_key="skipdb",
            source_title_key=source_title_key,
            source_episode_key=source_episode_key,
            source_status=status,
            quality_score=quality_score,
            votes_up=votes_up,
            votes_down=votes_down,
            payload_sha256=digest,
            normalization_status=normalization_status,
            normalization_reason=normalization_reason,
            normalized_anchor_id=normalized_anchor_id,
            normalized_episode_key=normalized_episode_key,
            metadata=metadata,
        )

        if valid_range:
            assert (
                segment_type is not None and start_ms is not None and end_ms is not None
            )
            writer.add_evidence_segment(
                record_id,
                source_segment_id=source_segment_id,
                segment_type=segment_type,
                start_ms=start_ms,
                end_ms=end_ms,
                media_duration_ms=media_duration_ms,
            )
            stats.evidence_segments += 1

        if status != "approved":
            if valid_range:
                stats.skipped_status += 1
            continue
        if not valid_range:
            continue

        if runtime_episode_id is not None and resolution is not None:
            writer.add_segment(
                episode_id=runtime_episode_id,
                source_id=source_id,
                lineage_id=lineage_id,
                source_segment_id=source_segment_id,
                segment_type=segment_type,
                start_ms=start_ms,
                end_ms=end_ms,
                media_duration_ms=media_duration_ms,
                quality_score=quality_score,
                mapping_method=resolution.method,
                mapping_confidence=resolution.confidence,
                votes_up=votes_up,
                votes_down=votes_down,
            )
            stats.runtime_segments += 1
            if resolution.method == "inferred-season-offset":
                stats.runtime_segments_inferred += 1
            else:
                stats.runtime_segments_exact += 1
        elif imdb_id in anime_imdb_ids:
            writer.add_source_segment(
                source_id=source_id,
                lineage_id=lineage_id,
                source_title_key=source_title_key,
                source_episode_key=source_episode_key,
                source_segment_id=source_segment_id,
                segment_type=segment_type,
                start_ms=start_ms,
                end_ms=end_ms,
                media_duration_ms=media_duration_ms,
            )
            stats.source_only_segments += 1
            stats.anime_source_only_segments += 1

        if index and index % 5000 == 0:
            writer.commit()

    stats.anime_titles_detected = len(anime_imdb_ids)
    writer.set_snapshot_record_count(snapshot_id, stats.records)
    writer.commit()
    return stats


def import_baha(
    path: Path,
    *,
    writer: DatabaseWriter,
    snapshot_id: int,
) -> ImportStats:
    stats = ImportStats(source=BAHA.key)
    source_id = writer.source_id(BAHA)
    lineage_id = writer.lineage_id(
        "baha",
        "Baha Anime Skip",
        "Baha Anime Skip project's manually curated/derived episode skip ranges.",
    )

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Baha Anime Skip database must be a JSON object")

    for video_sn, chapter_map in payload.items():
        if not isinstance(chapter_map, dict):
            stats.invalid += 1
            continue
        for raw_type, raw_range in chapter_map.items():
            stats.records += 1
            segment_type = _BAHA_TYPES.get(
                str(raw_type).upper(), str(raw_type).casefold()
            )
            valid = (
                isinstance(raw_range, list)
                and len(raw_range) == 2
                and _safe_float(raw_range[0]) is not None
                and _safe_float(raw_range[1]) is not None
            )
            start_ms = 0
            end_ms = 0
            if valid:
                start_sec = float(raw_range[0])
                duration_sec = float(raw_range[1])
                start_ms = round(start_sec * 1000)
                end_ms = round((start_sec + duration_sec) * 1000)
                valid = start_ms >= 0 and end_ms > start_ms

            source_segment_id = f"baha:{video_sn}:{raw_type}"
            record_key = source_segment_id
            record_id = writer.add_evidence_record(
                snapshot_id=snapshot_id,
                record_key=record_key,
                lineage_key="baha",
                source_episode_key=str(video_sn),
                payload_sha256=_payload_hash({raw_type: raw_range}),
                normalization_status="source-only" if valid else "invalid",
                normalization_reason=(
                    "upstream videoSn has no reusable bulk cross-database episode identity"
                    if valid
                    else "invalid Baha [start,duration] range"
                ),
                metadata={"chapter_type": str(raw_type)},
            )
            if not valid:
                stats.invalid += 1
                continue

            writer.add_evidence_segment(
                record_id,
                source_segment_id=source_segment_id,
                segment_type=segment_type,
                start_ms=start_ms,
                end_ms=end_ms,
            )
            writer.add_source_segment(
                source_id=source_id,
                lineage_id=lineage_id,
                source_title_key="",
                source_episode_key=str(video_sn),
                source_segment_id=source_segment_id,
                segment_type=segment_type,
                start_ms=start_ms,
                end_ms=end_ms,
            )
            stats.evidence_segments += 1
            stats.source_only_segments += 1
            stats.mapped += 1

    writer.set_snapshot_record_count(snapshot_id, stats.records)
    writer.commit()
    return stats
