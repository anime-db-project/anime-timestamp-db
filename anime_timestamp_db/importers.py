from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from anime_timestamp_db.anibridge import AniBridgeIndex, EpisodeTarget
from anime_timestamp_db.config import ANISKIP, BAHA, SKIPDB
from anime_timestamp_db.database import DatabaseWriter, IdentityConflict

_SKIPDB_TYPES = {
    "intro": "opening",
    "recap": "recap",
    "outro": "ending",
    "preview": "preview",
}
_ANISKIP_TYPES = {
    "op": "opening",
    "ed": "ending",
    "mixed-op": "mixed-opening",
    "mixed-ed": "mixed-ending",
    "recap": "recap",
    "preview": "preview",
}
_BAHA_TYPES = {
    "OP": "opening",
    "ED": "ending",
}
_PROVIDER_PRIORITY = {"mal": 0, "anilist": 1, "anidb": 2}


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


def _episode_number(value: object) -> tuple[str, float] | None:
    parsed = _safe_float(value)
    if parsed is None or parsed < 0:
        return None
    if parsed.is_integer():
        return str(int(parsed)), float(int(parsed))
    text = format(parsed, ".15g")
    return text, parsed


def _normalize_aniskip_type(value: object) -> str | None:
    raw = str(value or "").strip().casefold().replace("_", "-")
    if not raw:
        return None
    return _ANISKIP_TYPES.get(raw, raw)


def _normalize_episode_targets(
    targets: tuple[EpisodeTarget, ...],
) -> tuple[dict[str, str], int, str, bool] | None:
    """Reduce explicit AniBridge targets to one coherent anime episode identity."""

    if not targets:
        return None

    by_provider: dict[str, set[tuple[str, str | None, int]]] = {}
    for target in targets:
        by_provider.setdefault(target.descriptor.provider, set()).add(
            (
                target.descriptor.external_id,
                target.descriptor.scope,
                target.episode_number,
            )
        )
    if any(len(values) != 1 for values in by_provider.values()):
        return None

    flattened = {
        provider: next(iter(values)) for provider, values in by_provider.items()
    }
    regular_numbers = {
        episode_number
        for provider, (_, _scope, episode_number) in flattened.items()
        if provider in {"mal", "anilist"}
    }
    if len(regular_numbers) > 1:
        return None

    title_ids = {
        provider: external_id
        for provider, (external_id, _scope, _episode_number) in flattened.items()
    }
    if regular_numbers:
        episode_number = next(iter(regular_numbers))
        return title_ids, episode_number, f"ep:{episode_number}", False

    anidb = flattened.get("anidb")
    if anidb is None:
        return None
    _external_id, scope, episode_number = anidb
    normalized_scope = (scope or "R").upper()
    if normalized_scope == "R":
        return title_ids, episode_number, f"ep:{episode_number}", False
    return (
        title_ids,
        episode_number,
        f"anidb:{normalized_scope}:{episode_number}",
        True,
    )


def import_aniskip(
    path: Path,
    *,
    writer: DatabaseWriter,
    snapshot_id: int,
) -> ImportStats:
    """Import AniSkip's official sanitized public CSV as MAL-native timestamps."""

    stats = ImportStats(source=ANISKIP.key)
    source_id = writer.source_id(ANISKIP)
    lineage_id = writer.lineage_id(
        "aniskip",
        "AniSkip",
        "Official sanitized public AniSkip timing dataset.",
    )

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        required = {
            "id",
            "episode_length",
            "skip_type",
            "skip_time_start",
            "skip_time_end",
            "mal_id",
            "episode_number",
            "external_id",
        }
        if rows.fieldnames is None or not required.issubset(set(rows.fieldnames)):
            raise ValueError(
                "AniSkip CSV is missing required columns: "
                + ", ".join(sorted(required - set(rows.fieldnames or ())))
            )

        for index, raw in enumerate(rows):
            stats.records += 1
            safe_raw = {key: value for key, value in raw.items() if key != "user_id"}
            mal_id_int = _safe_int(raw.get("mal_id"), minimum=1)
            episode = _episode_number(raw.get("episode_number"))
            segment_type = _normalize_aniskip_type(raw.get("skip_type"))
            start_sec = _safe_float(raw.get("skip_time_start"))
            end_sec = _safe_float(raw.get("skip_time_end"))
            episode_length_sec = _safe_float(raw.get("episode_length"))
            external_id = str(raw.get("external_id") or "").strip()
            row_id = str(raw.get("id") or index).strip()
            source_segment_id = f"aniskip:{external_id or row_id}"

            valid = (
                mal_id_int is not None
                and episode is not None
                and segment_type is not None
                and start_sec is not None
                and end_sec is not None
                and start_sec >= 0
                and end_sec > start_sec
            )
            start_ms = round((start_sec or 0.0) * 1000)
            end_ms = round((end_sec or 0.0) * 1000)
            media_duration_ms = (
                round(episode_length_sec * 1000)
                if episode_length_sec is not None and episode_length_sec > 0
                else None
            )
            valid = bool(valid and end_ms > start_ms)

            if valid:
                assert mal_id_int is not None and episode is not None
                mal_id = str(mal_id_int)
                episode_text, episode_value = episode
                episode_key = f"ep:{episode_text}"
                normalization_status = "mapped"
                normalization_reason = "native MAL title and episode identity"
                stats.mapped += 1

                try:
                    title_id = writer.get_or_create_title({"mal": mal_id})
                    episode_id = writer.get_or_create_episode(
                        title_id,
                        episode_key=episode_key,
                        episode_number=episode_value,
                        duration_ms=media_duration_ms,
                    )
                    writer.add_episode_ref(
                        source_id,
                        source_title_key=mal_id,
                        source_episode_key=episode_text,
                        episode_id=episode_id,
                        source_episode_number_text=episode_text,
                    )
                    existing = writer.conn.execute(
                        """
                        SELECT episode_id FROM episode_ids
                        WHERE provider='mal' AND title_external_id=?
                          AND scope='' AND episode_number_text=?
                        """,
                        (mal_id, episode_text),
                    ).fetchone()
                    if existing is not None and int(existing[0]) != episode_id:
                        raise IdentityConflict(
                            f"MAL {mal_id} episode {episode_text} maps to multiple episodes"
                        )
                    writer.conn.execute(
                        """
                        INSERT OR IGNORE INTO episode_ids(
                            provider, title_external_id, scope,
                            episode_number_text, episode_id
                        ) VALUES ('mal', ?, '', ?, ?)
                        """,
                        (mal_id, episode_text, episode_id),
                    )
                except IdentityConflict as exc:
                    normalization_status = "ambiguous"
                    normalization_reason = str(exc)
                    stats.mapped -= 1
                    stats.ambiguous += 1
                    episode_id = None
                normalized_id = mal_id if normalization_status == "mapped" else ""
                normalized_episode_key = (
                    episode_key if normalization_status == "mapped" else ""
                )
            else:
                mal_id = str(mal_id_int or "")
                episode_text = episode[0] if episode is not None else ""
                normalization_status = "invalid"
                normalization_reason = (
                    "missing MAL/episode/type or invalid timestamp range"
                )
                normalized_id = ""
                normalized_episode_key = ""
                episode_id = None
                stats.invalid += 1

            record_id = writer.add_evidence_record(
                snapshot_id=snapshot_id,
                record_key=source_segment_id,
                lineage_key="aniskip",
                source_title_key=mal_id,
                source_episode_key=episode_text,
                source_status="public-sanitized",
                payload_sha256=_payload_hash(safe_raw),
                normalization_status=normalization_status,
                normalization_reason=normalization_reason,
                normalized_provider="mal" if normalized_id else "",
                normalized_id=normalized_id,
                normalized_episode_key=normalized_episode_key,
                metadata={
                    "upstream_id": row_id,
                    "created_at": str(raw.get("created_at") or ""),
                    "updated_at": str(raw.get("updated_at") or ""),
                    "raw_skip_type": str(raw.get("skip_type") or ""),
                },
            )

            if valid:
                assert segment_type is not None
                writer.add_evidence_segment(
                    record_id,
                    source_segment_id=source_segment_id,
                    segment_type=segment_type,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    media_duration_ms=media_duration_ms,
                )
                stats.evidence_segments += 1

            if episode_id is not None and valid:
                writer.add_segment(
                    episode_id=episode_id,
                    source_id=source_id,
                    lineage_id=lineage_id,
                    source_segment_id=source_segment_id,
                    segment_type=segment_type,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    media_duration_ms=media_duration_ms,
                )
                stats.runtime_segments += 1

            if index and index % 5000 == 0:
                writer.commit()

    writer.set_snapshot_record_count(snapshot_id, stats.records)
    writer.commit()
    return stats


def import_skipdb(
    path: Path,
    *,
    writer: DatabaseWriter,
    snapshot_id: int,
    mappings: AniBridgeIndex,
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
        normalization_status = "unprocessed"
        normalization_reason = ""
        normalized_provider = ""
        normalized_id = ""
        normalized_episode_key = ""
        runtime_target: tuple[int, str] | None = None

        if not valid_range:
            normalization_status = "invalid"
            normalization_reason = "missing identifier/type or invalid timestamp range"
            stats.invalid += 1
        else:
            ids: dict[str, str] = {}
            episode_number: int | None = None
            episode_key = ""
            is_special = False

            if media_type == "series" and season is not None and episode is not None:
                mapping = mappings.resolve_series_episode(imdb_id, season, episode)
                stats.skipped_complex_mappings += mapping.skipped_complex_targets
                normalized = _normalize_episode_targets(mapping.targets)
                if normalized is not None:
                    ids, episode_number, episode_key, is_special = normalized
            elif media_type == "movie":
                movie_targets = mappings.resolve_movie(imdb_id)
                per_provider: dict[str, set[str]] = {}
                for descriptor in movie_targets:
                    per_provider.setdefault(descriptor.provider, set()).add(
                        descriptor.external_id
                    )
                if per_provider and all(
                    len(values) == 1 for values in per_provider.values()
                ):
                    ids = {
                        provider: next(iter(values))
                        for provider, values in per_provider.items()
                    }
                    ids["imdb_movie"] = imdb_id
                    episode_number = 1
                    episode_key = "movie"

            if ids and episode_number is not None and episode_key:
                canonical_provider = min(
                    ids, key=lambda p: _PROVIDER_PRIORITY.get(p, 99)
                )
                normalization_status = "mapped"
                normalization_reason = "AniBridge one-to-one episode mapping"
                normalized_provider = canonical_provider
                normalized_id = ids[canonical_provider]
                normalized_episode_key = episode_key
                stats.mapped += 1

                if status == "approved":
                    try:
                        title_id = writer.get_or_create_title(
                            ids, display_title=display_title
                        )
                        episode_id = writer.get_or_create_episode(
                            title_id,
                            episode_key=episode_key,
                            episode_number=episode_number,
                            is_special=is_special,
                        )
                        writer.add_episode_ref(
                            source_id,
                            source_title_key=source_title_key,
                            source_episode_key=source_episode_key,
                            episode_id=episode_id,
                            source_episode_number_text=(
                                "" if episode is None else str(episode)
                            ),
                        )
                    except IdentityConflict as exc:
                        normalization_status = "ambiguous"
                        normalization_reason = str(exc)
                        normalized_provider = ""
                        normalized_id = ""
                        normalized_episode_key = ""
                        stats.ambiguous += 1
                    else:
                        runtime_target = (episode_id, episode_key)
            else:
                normalization_status = "unmapped"
                normalization_reason = (
                    "no safe one-to-one AniBridge anime episode mapping"
                )
                stats.unmapped += 1

        metadata = {
            "media_type": media_type,
            "season": season,
            "episode": episode,
            "title": display_title,
            "created_at": str(raw.get("created_at") or ""),
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
            normalized_provider=normalized_provider,
            normalized_id=normalized_id,
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
        if runtime_target is None or not valid_range:
            continue

        episode_id, _episode_key = runtime_target
        writer.add_segment(
            episode_id=episode_id,
            source_id=source_id,
            lineage_id=lineage_id,
            source_segment_id=source_segment_id,
            segment_type=segment_type,
            start_ms=start_ms,
            end_ms=end_ms,
            media_duration_ms=media_duration_ms,
            quality_score=quality_score,
            votes_up=votes_up,
            votes_down=votes_down,
        )
        stats.runtime_segments += 1

        if index and index % 5000 == 0:
            writer.commit()

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
