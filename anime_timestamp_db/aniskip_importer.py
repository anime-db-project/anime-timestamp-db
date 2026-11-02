from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from anime_timestamp_db.config import ANISKIP
from anime_timestamp_db.database import DatabaseWriter, IdentityConflict
from anime_timestamp_db.importers import ImportStats

_CURRENT_FIELDS = {
    "anime_id",
    "episode_number",
    "provider_name",
    "skip_type",
    "votes",
    "start_time",
    "end_time",
    "episode_length",
    "submit_date",
}
_LEGACY_FIELDS = {
    "id",
    "episode_length",
    "skip_type",
    "skip_time_start",
    "skip_time_end",
    "mal_id",
    "episode_number",
    "external_id",
}
_TYPE_MAP = {
    "op": "opening",
    "ed": "ending",
    "mixed-op": "mixed-opening",
    "mixed-ed": "mixed-ending",
    "recap": "recap",
    "preview": "preview",
}


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
    return format(parsed, ".15g"), parsed


def _segment_type(value: object) -> str | None:
    raw = str(value or "").strip().casefold().replace("_", "-")
    if not raw:
        return None
    return _TYPE_MAP.get(raw, raw)


def _detect_schema(fieldnames: list[str] | None) -> str:
    fields = set(fieldnames or ())
    if _CURRENT_FIELDS.issubset(fields):
        return "current"
    if _LEGACY_FIELDS.issubset(fields):
        return "legacy"
    expected = sorted(_CURRENT_FIELDS | _LEGACY_FIELDS)
    raise ValueError(
        "Unsupported AniSkip CSV schema. "
        f"Columns received: {sorted(fields)}. Known columns include: {expected}"
    )


def import_aniskip(
    path: Path,
    *,
    writer: DatabaseWriter,
    snapshot_id: int,
) -> ImportStats:
    """Import AniSkip's official sanitized public CSV as MAL-native timestamps.

    The public dump has changed shape over time. Both the current sanitized seed
    format and the older export format are accepted. ``anime_id`` in the current
    format is the MAL ID used by AniSkip's API.
    """

    stats = ImportStats(source=ANISKIP.key)
    source_id = writer.source_id(ANISKIP)
    lineage_id = writer.lineage_id(
        "aniskip",
        "AniSkip",
        "Official sanitized public AniSkip timing dataset.",
    )
    duplicate_hashes: dict[str, int] = {}

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        schema_variant = _detect_schema(rows.fieldnames)

        for index, raw in enumerate(rows):
            stats.records += 1
            safe_raw = {key: value for key, value in raw.items() if key != "user_id"}
            digest = _canonical_hash(safe_raw)
            duplicate_index = duplicate_hashes.get(digest, 0)
            duplicate_hashes[digest] = duplicate_index + 1

            if schema_variant == "current":
                mal_id_int = _safe_int(raw.get("anime_id"), minimum=1)
                start_sec = _safe_float(raw.get("start_time"))
                end_sec = _safe_float(raw.get("end_time"))
                provider_name = str(raw.get("provider_name") or "").strip()
                raw_votes = _safe_int(raw.get("votes")) or 0
                submitted_at = str(raw.get("submit_date") or "").strip()
                base_segment_id = digest
                created_at = submitted_at
                updated_at = ""
            else:
                mal_id_int = _safe_int(raw.get("mal_id"), minimum=1)
                start_sec = _safe_float(raw.get("skip_time_start"))
                end_sec = _safe_float(raw.get("skip_time_end"))
                provider_name = ""
                raw_votes = 0
                submitted_at = ""
                external_id = str(raw.get("external_id") or "").strip()
                row_id = str(raw.get("id") or index).strip()
                base_segment_id = external_id or row_id or digest
                created_at = str(raw.get("created_at") or "").strip()
                updated_at = str(raw.get("updated_at") or "").strip()

            episode = _episode_number(raw.get("episode_number"))
            segment_type = _segment_type(raw.get("skip_type"))
            episode_length_sec = _safe_float(raw.get("episode_length"))
            suffix = f":{duplicate_index}" if duplicate_index else ""
            source_segment_id = f"aniskip:{base_segment_id}{suffix}"
            votes_up = max(0, raw_votes)
            votes_down = max(0, -raw_votes)

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

            mal_id = str(mal_id_int or "")
            episode_text = episode[0] if episode is not None else ""
            episode_id: int | None = None

            if valid:
                assert mal_id_int is not None and episode is not None
                mal_id = str(mal_id_int)
                episode_text, episode_value = episode
                episode_key = f"ep:{episode_text}"
                normalization_status = "mapped"
                normalization_reason = "native MAL title and episode identity"

                writer.conn.execute("SAVEPOINT aniskip_row")
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
                    writer.conn.execute("ROLLBACK TO aniskip_row")
                    writer.conn.execute("RELEASE aniskip_row")
                    episode_id = None
                    normalization_status = "ambiguous"
                    normalization_reason = str(exc)
                    stats.ambiguous += 1
                else:
                    writer.conn.execute("RELEASE aniskip_row")
                    stats.mapped += 1

                normalized_id = mal_id if episode_id is not None else ""
                normalized_episode_key = episode_key if episode_id is not None else ""
            else:
                normalization_status = "invalid"
                normalization_reason = "missing MAL/episode/type or invalid timestamp range"
                normalized_id = ""
                normalized_episode_key = ""
                stats.invalid += 1

            record_id = writer.add_evidence_record(
                snapshot_id=snapshot_id,
                record_key=source_segment_id,
                lineage_key="aniskip",
                source_title_key=mal_id,
                source_episode_key=episode_text,
                source_status="public-sanitized",
                quality_score=None,
                votes_up=votes_up,
                votes_down=votes_down,
                payload_sha256=digest,
                normalization_status=normalization_status,
                normalization_reason=normalization_reason,
                normalized_provider="mal" if normalized_id else "",
                normalized_id=normalized_id,
                normalized_episode_key=normalized_episode_key,
                metadata={
                    "schema_variant": schema_variant,
                    "provider_name": provider_name,
                    "raw_votes": raw_votes,
                    "submitted_at": submitted_at,
                    "created_at": created_at,
                    "updated_at": updated_at,
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
                    votes_up=votes_up,
                    votes_down=votes_down,
                )
                stats.runtime_segments += 1

            if index and index % 5000 == 0:
                writer.commit()

    writer.set_snapshot_record_count(snapshot_id, stats.records)
    writer.commit()
    return stats
