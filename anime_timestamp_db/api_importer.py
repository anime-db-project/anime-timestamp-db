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

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.api_episode_bridge import AnimeSkipEpisodeBridge
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
    anibridge: AniBridgeIndex | None = None,
) -> ImportStats:
    if source not in ("aniskip", "anime_skip"):
        raise ValueError("Unknown API checkpoint source")
    state = _read(path, source)
    spec = ANISKIP_API if source == "aniskip" else ANIME_SKIP_API
    source_id = writer.source_id(spec)
    stats = ImportStats(source=spec.key)
    seen: set[str] = set()
    episode_bridge = (
        AnimeSkipEpisodeBridge(anibridge, identities)
        if source == "anime_skip" and anibridge is not None
        else None
    )
    bridged_episodes: set[tuple[str, int]] = set()

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
            mapping_method = "verified-native-api"
            bridge_proof = None
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
                # A season-local number is never assumed to be a MAL episode.
                # Only independently indexed AniList episodes or a one-to-one
                # AniBridge AniDB:R -> AniList+MAL proof may be normalized.
                proven = bool(item.get("episode_identity_proven"))
                unambiguous_uuid = len(episode_uuids[(native_id, episode)]) <= 1
                native_conflict = False
                if proven and unambiguous_uuid:
                    if episode_bridge is not None:
                        bridge_proof = episode_bridge.resolve(
                            native_id, anchor, episode
                        )
                    indexed = writer.conn.execute(
                        """SELECT ei.episode_id, ep.episode_key
                           FROM episode_ids ei
                           JOIN episodes ep ON ep.id=ei.episode_id
                           WHERE ei.anchor_id=? AND ei.provider='anilist'
                             AND ei.scope='' AND ei.episode_number_text=?""",
                        (anchor, str(episode)),
                    ).fetchone()
                    if indexed is not None:
                        indexed_episode, indexed_key = int(indexed[0]), str(indexed[1])
                        if (
                            bridge_proof is not None
                            and indexed_key != bridge_proof.episode_key
                        ):
                            native_conflict = True
                            normalization_reason = "AniBridge episode proof conflicts with native episode index"
                            stats.ambiguous += 1
                        else:
                            candidate_episode_id = indexed_episode
                            normalized_episode_key = indexed_key
                    elif bridge_proof is not None:
                        writer.conn.execute("SAVEPOINT api_bridge_episode")
                        try:
                            writer.get_or_create_title(anchor)
                            candidate_episode_id = writer.get_or_create_episode(
                                anchor,
                                episode_key=bridge_proof.episode_key,
                                episode_number=bridge_proof.mal_episode,
                                duration_ms=duration,
                            )
                            writer.add_episode_id(
                                episode_id=candidate_episode_id,
                                anchor_id=anchor,
                                provider="anilist",
                                episode_number=episode,
                            )
                            writer.add_episode_id(
                                episode_id=candidate_episode_id,
                                anchor_id=anchor,
                                provider="mal",
                                episode_number=bridge_proof.mal_episode,
                            )
                            writer.add_episode_id(
                                episode_id=candidate_episode_id,
                                anchor_id=anchor,
                                provider="anidb",
                                scope="R",
                                episode_number=bridge_proof.anidb_episode,
                            )
                        except (ValueError, IdentityConflict):
                            writer.conn.execute("ROLLBACK TO api_bridge_episode")
                            candidate_episode_id = None
                            native_conflict = True
                            stats.ambiguous += 1
                            normalization_reason = "AniBridge episode proof conflicts with an existing episode"
                        else:
                            normalized_episode_key = bridge_proof.episode_key
                        finally:
                            writer.conn.execute("RELEASE api_bridge_episode")

                    if candidate_episode_id is not None:
                        writer.conn.execute("SAVEPOINT api_episode_ref")
                        try:
                            writer.add_episode_ref(
                                source_id,
                                source_title_key=native_id,
                                source_episode_key=source_episode_key,
                                episode_id=candidate_episode_id,
                                source_episode_number_text=str(episode),
                            )
                        except (ValueError, IdentityConflict):
                            writer.conn.execute("ROLLBACK TO api_episode_ref")
                            candidate_episode_id = None
                            native_conflict = True
                            stats.ambiguous += 1
                            normalization_reason = "Conflicting native episode UUID"
                        finally:
                            writer.conn.execute("RELEASE api_episode_ref")
                if candidate_episode_id is not None and bridge_proof is not None:
                    mapping_method = "exact-anibridge-api"
                    if (native_id, episode) not in bridged_episodes:
                        bridged_episodes.add((native_id, episode))
                        stats.exact_episode_mappings += 1
                    stats.runtime_segments_exact += 1
                if candidate_episode_id is None:
                    if not native_conflict:
                        normalization_reason = (
                            "AniList episode lacks independent episode identity"
                        )
                    stats.unmapped += 1

            if candidate_episode_id is not None:
                normalization_status = "mapped"
                normalization_reason = (
                    "Verified exact AniBridge AniDB:R to AniList/MAL episode mapping"
                    if mapping_method == "exact-anibridge-api"
                    else "Verified native provider episode identity"
                )
                stats.mapped += 1
            evidence_metadata = {
                "checkpoint_source": source,
                "checked_at": str(record.get("checked_at") or ""),
                "upstream_lineage": str(item.get("upstream_lineage") or ""),
                "upstream_episode_id": upstream_episode_id,
                "season": item.get("season"),
                "absolute_number": item.get("absolute_number"),
                "episode_identity_proven": item.get("episode_identity_proven"),
                "consensus_eligible": consensus_eligible,
            }
            if candidate_episode_id is not None and bridge_proof is not None:
                evidence_metadata["bridge_proof"] = {
                    "method": "anibridge-anidb-r",
                    "mal_id": bridge_proof.mal_id,
                    "mal_episode": bridge_proof.mal_episode,
                    "anidb_id": bridge_proof.anidb_id,
                    "anidb_episode": bridge_proof.anidb_episode,
                }
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
                metadata=evidence_metadata,
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
                    mapping_method=mapping_method,
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
