"""Auditable import of previously collected API checkpoints.

Only called for explicitly authorized release builds. The mapping database is
the source of truth; cached AMDB anchors are never trusted. AniSkip's MAL
episode numbering is native, while Anime Skip/AniList episode numbering does
NOT imply that the same MAL episode is the same playback unit.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from anime_timestamp_db.config import ANIME_SKIP_API, ANISKIP_API
from anime_timestamp_db.database import DatabaseWriter, IdentityConflict
from anime_timestamp_db.importers import ImportStats
from anime_timestamp_db.mapping_identity import MappingAnchorIndex

TYPES = {
    "opening",
    "ending",
    "recap",
    "filler",
    "preview",
    "mixed-opening",
    "mixed-ending",
    "transition",
    "branding",
    "title_card",
}
MAX_EPISODE_MS = 43_200_000  # 12 hours, safety bound, not an assumed duration.
LINEAGES = {
    "ANIME_SKIP": ("anime-skip", "Anime Skip", True),
    "ANISKIP": ("aniskip", "AniSkip", True),
    "BETTER_VRV": ("better-vrv", "BetterVRV", True),
}


def _int(value: object, minimum: int = 1) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    if str(value) != str(result) or result < minimum:
        return None
    return result


def _hash(record: dict) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _lineage(source: str, value: object) -> tuple[str, str, bool]:
    if source == "aniskip":
        return "aniskip", "AniSkip", True
    code = str(value or "").strip().upper().replace("-", "_")
    if code in LINEAGES:
        return LINEAGES[code]
    # Unknown mirrors are queryable but must never cast consensus votes.
    return "anime-skip-unknown", "Anime Skip (unknown upstream)", False


def _read(path: Path, source: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        state = json.load(stream)
    if (
        not isinstance(state, dict)
        or state.get("version") != 1
        or state.get("source") != source
        or not isinstance(state.get("records"), dict)
    ):
        raise ValueError(f"Invalid API checkpoint {path}")
    return state


def import_api_checkpoint(
    path: Path,
    *,
    source: str,
    writer: DatabaseWriter,
    snapshot_id: int,
    identities: MappingAnchorIndex,
) -> ImportStats:
    if source not in ("aniskip", "anime_skip"):
        raise ValueError("Unknown API checkpoint source")
    state = _read(path, source)
    spec = ANISKIP_API if source == "aniskip" else ANIME_SKIP_API
    source_id = writer.source_id(spec)
    stats = ImportStats(source=spec.key)
    seen: set[str] = set()

    # Disallow normalization when a title contains conflicting Anime Skip
    # upstream episode UUIDs for the same purported numeric episode.
    episode_uuids: dict[tuple[str, int], set[str]] = defaultdict(set)
    if source == "anime_skip":
        for key, record in state["records"].items():
            if not isinstance(record, dict):
                continue
            for item in record.get("segments", []):
                if not isinstance(item, dict) or item.get("native_title_id") != key:
                    continue
                n = _int(item.get("episode"))
                if n is not None and item.get("upstream_episode_id"):
                    episode_uuids[(key, n)].add(str(item["upstream_episode_id"]))

    for key, record in sorted(state["records"].items()):
        if not isinstance(record, dict) or record.get("status") != "found":
            continue
        if source == "aniskip":
            parts = key.split(":")
            if len(parts) != 2 or _int(parts[0]) is None or _int(parts[1]) is None:
                stats.invalid += 1
                continue
            native_id, key_episode = parts[0], int(parts[1])
            provider = "mal"
        else:
            if _int(key) is None:
                stats.invalid += 1
                continue
            native_id, key_episode = key, None
            provider = "anilist"

        anchor = identities.anchor_for(provider, native_id)
        segments = record.get("segments")
        if not isinstance(segments, list):
            stats.invalid += 1
            continue

        for item in segments:
            stats.records += 1
            if not isinstance(item, dict):
                stats.invalid += 1
                continue
            episode = _int(item.get("episode"))
            start = _int(item.get("start_ms"), minimum=0)
            end = _int(item.get("end_ms"), minimum=1)
            kind = item.get("type")
            if (
                item.get("source") != source
                or item.get("native_title_id") != native_id
                or episode is None
                or (key_episode is not None and key_episode != episode)
                or start is None
                or end is None
                or not start < end <= MAX_EPISODE_MS
                or not isinstance(kind, str)
                or kind not in TYPES
            ):
                stats.invalid += 1
                continue
            raw_duration = _int(item.get("duration_ms"))
            duration = (
                raw_duration
                if raw_duration is not None and raw_duration <= MAX_EPISODE_MS
                else None
            )
            # An incorrect duration must not be used to silently shift boundaries.
            if duration is not None and end > duration + 30_000:
                stats.invalid += 1
                continue

            upstream_episode_id = str(item.get("upstream_episode_id") or "")
            seg_uuid = str(item.get("source_segment_id") or "")
            if not seg_uuid:
                seg_uuid = "derived-" + _hash(item)[:28]
            # Provider + title + episode / source episode UUID must disambiguate
            # IDs even if upstream recycles a segment identifier.
            source_segment_id = (
                f"{source}:{native_id}:{upstream_episode_id or episode}:{seg_uuid}"
            )
            if source_segment_id in seen:
                continue
            seen.add(source_segment_id)
            lineage_key, lineage_name, consensus_eligible = _lineage(
                source, item.get("upstream_lineage")
            )
            lineage_id = writer.lineage_id(
                lineage_key,
                lineage_name,
                "API upstream identity; mirrors share their original consensus lineage.",
            )

            source_episode_key = (
                str(episode)
                if source == "aniskip"
                else upstream_episode_id or f"ep:{episode}"
            )
            candidate_episode_id = None
            normalized_episode_key = ""
            normalization_status = "source-only"
            normalization_reason = "Native episode cannot be independently normalized"
            if anchor is None:
                normalization_reason = "Title no longer has unambiguous AMDB identity"
                stats.unmapped += 1
            elif source == "aniskip":
                writer.conn.execute("SAVEPOINT api_row")
                try:
                    writer.get_or_create_title(anchor)
                    candidate_episode_id = writer.get_or_create_episode(
                        anchor,
                        episode_key=f"ep:{episode}",
                        episode_number=episode,
                        duration_ms=duration,
                    )
                    writer.add_episode_ref(
                        source_id,
                        source_title_key=native_id,
                        source_episode_key=source_episode_key,
                        episode_id=candidate_episode_id,
                        source_episode_number_text=str(episode),
                    )
                    writer.add_episode_id(
                        episode_id=candidate_episode_id,
                        anchor_id=anchor,
                        provider="mal",
                        scope="",
                        episode_number=episode,
                    )
                except (ValueError, IdentityConflict):
                    writer.conn.execute("ROLLBACK TO api_row")
                    stats.ambiguous += 1
                    candidate_episode_id = None
                    normalization_reason = "MAL episode identity conflict"
                else:
                    normalized_episode_key = f"ep:{episode}"
                finally:
                    writer.conn.execute("RELEASE api_row")
            else:
                # AniList per-season numbers are NOT necessarily MAL "ep:N".
                # Only link to an episode already independently verified and
                # indexed by the native AniList episode numbering.
                proven = bool(item.get("episode_identity_proven"))
                if proven and len(episode_uuids[(native_id, episode)]) <= 1:
                    result = writer.conn.execute(
                        """SELECT episode_id FROM episode_ids
                           WHERE anchor_id=? AND provider='anilist'
                             AND scope='' AND episode_number_text=?""",
                        (anchor, str(episode)),
                    ).fetchone()
                    if result is not None:
                        candidate_episode_id = int(result[0])
                        key_row = writer.conn.execute(
                            "SELECT episode_key FROM episodes WHERE id=?",
                            (candidate_episode_id,),
                        ).fetchone()
                        if key_row:
                            normalized_episode_key = key_row[0]
                            writer.add_episode_ref(
                                source_id,
                                source_title_key=native_id,
                                source_episode_key=source_episode_key,
                                episode_id=candidate_episode_id,
                                source_episode_number_text=str(episode),
                            )
                if candidate_episode_id is None:
                    normalization_reason = "AniList episode number not independently linked to canonical episode"
                    stats.unmapped += 1

            if candidate_episode_id is not None:
                normalization_status = "mapped"
                normalization_reason = "Verified native provider episode identity"
                stats.mapped += 1
            record_id = writer.add_evidence_record(
                snapshot_id=snapshot_id,
                record_key=source_segment_id,
                lineage_key=lineage_key,
                source_title_key=native_id,
                source_episode_key=source_episode_key,
                source_status="live-api-checkpoint",
                payload_sha256=_hash(item),
                normalization_status=normalization_status,
                normalization_reason=normalization_reason,
                normalized_anchor_id=anchor,
                normalized_episode_key=normalized_episode_key,
                metadata={
                    "checkpoint_source": source,
                    "checked_at": str(record.get("checked_at") or ""),
                    "upstream_lineage": str(item.get("upstream_lineage") or ""),
                    "upstream_episode_id": upstream_episode_id,
                    "season": item.get("season"),
                    "absolute_number": item.get("absolute_number"),
                    "episode_identity_proven": item.get("episode_identity_proven"),
                    "consensus_eligible": consensus_eligible,
                },
            )
            writer.add_evidence_segment(
                record_id,
                source_segment_id=source_segment_id,
                segment_type=kind,
                start_ms=start,
                end_ms=end,
                media_duration_ms=duration,
            )
            stats.evidence_segments += 1
            if candidate_episode_id is not None:
                writer.add_segment(
                    episode_id=candidate_episode_id,
                    source_id=source_id,
                    lineage_id=lineage_id,
                    source_segment_id=source_segment_id,
                    segment_type=kind,
                    start_ms=start,
                    end_ms=end,
                    media_duration_ms=duration,
                    mapping_method="verified-native-api",
                    consensus_eligible=consensus_eligible,
                )
                stats.runtime_segments += 1
            else:
                writer.add_source_segment(
                    source_id=source_id,
                    lineage_id=lineage_id,
                    source_title_key=native_id,
                    source_episode_key=source_episode_key,
                    source_segment_id=source_segment_id,
                    segment_type=kind,
                    start_ms=start,
                    end_ms=end,
                    media_duration_ms=duration,
                )
                stats.source_only_segments += 1
            if stats.records % 2500 == 0:
                writer.commit()
    writer.set_snapshot_record_count(snapshot_id, stats.records)
    writer.commit()
    return stats
