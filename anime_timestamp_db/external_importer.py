"""Auditable source-only imports from permissioned external API checkpoints.

The source's TVDB/TMDB/IMDb episode *order* does not prove equivalence to
the anime title's MAL/AniList numbering, so we never create canonical episodes.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.importers import ImportStats
from anime_timestamp_db.mapping_identity import MappingAnchorIndex

EXTERNAL_SOURCES = {
    "introdb": (
        "introdb-api",
        "IntroDB",
        "https://introdb.app/",
        "No bulk copy/redistribution without provider permission.",
    ),
    "publicmetadb": (
        "publicmetadb-api",
        "PublicMetaDB",
        "https://publicmetadb.com/",
        "API requires an owner-issued key; check dataset reuse terms.",
    ),
    "theintrodb": (
        "theintrodb-api",
        "TheIntroDB",
        "https://theintrodb.org/",
        "API read access is public; data redistribution rights must be verified.",
    ),
    "introhater": (
        "introhater-api",
        "IntroHater",
        "https://introhater.com/",
        "Automated scraping prohibited without provider permission.",
    ),
}
PROVIDERS = {
    "introdb": {"imdb"},
    "publicmetadb": {"tmdb_tv"},
    "theintrodb": {"tvdb", "imdb", "tmdb_tv"},
    "introhater": {"imdb"},
}
KINDS = {
    "opening",
    "ending",
    "recap",
    "preview",
    "post_credits",
}
MAX_MS = 43_200_000


def import_external_checkpoint(
    path: Path,
    *,
    source: str,
    writer: DatabaseWriter,
    snapshot_id: int,
    identities: MappingAnchorIndex,
) -> ImportStats:
    if source not in EXTERNAL_SOURCES:
        raise ValueError(f"Unknown external checkpoint {source}")
    with gzip.open(path, "rt", encoding="utf-8") as inp:
        state = json.load(inp)
    if not (
        isinstance(state, dict)
        and state.get("version") == 1
        and state.get("source") == source
        and isinstance(state.get("records"), dict)
    ):
        raise ValueError("Invalid source checkpoint envelope")
    from anime_timestamp_db.config import EXTERNAL_API_SPECS

    spec = EXTERNAL_API_SPECS[source]
    source_id = writer.source_id(spec)
    stats = ImportStats(source=spec.key)
    seen: set[str] = set()
    detected_titles: set[int] = set()

    for record_key, record in sorted(state["records"].items()):
        if not isinstance(record, dict) or record.get("status") != "found":
            continue
        if not isinstance(record.get("segments"), list):
            stats.invalid += 1
            continue
        for item in record["segments"]:
            stats.records += 1
            if not isinstance(item, dict) or item.get("source") != source:
                stats.invalid += 1
                continue
            provider = str(item.get("native_provider") or "")
            native = str(item.get("native_title_id") or "")
            season, episode = item.get("season"), item.get("episode")
            start, end = item.get("start_ms"), item.get("end_ms")
            kind = item.get("type")
            if (
                provider not in PROVIDERS[source]
                or not native
                or not isinstance(season, int)
                or isinstance(season, bool)
                or not isinstance(episode, int)
                or isinstance(episode, bool)
                or season < 0
                or episode < 1
                or record_key != f"{provider}:{native}:{season}:{episode}"
                or not isinstance(start, int)
                or isinstance(start, bool)
                or not isinstance(end, int)
                or isinstance(end, bool)
                or not 0 <= start < end <= MAX_MS
                or kind not in KINDS
            ):
                stats.invalid += 1
                continue
            anchor = identities.anchor_for(provider, native)
            if anchor is None:
                stats.unmapped += 1
                continue
            origin = str(item.get("upstream_lineage") or source).strip()
            if not origin:
                origin = source
            source_title_key = f"{provider}:{native}"
            source_episode_key = f"{season}:{episode}"
            identifier = str(item.get("source_segment_id") or "")
            if not identifier:
                stats.invalid += 1
                continue
            segment_key = (
                f"{source}:{source_title_key}:{source_episode_key}:{identifier}"
            )
            if segment_key in seen:
                continue
            seen.add(segment_key)
            # Retain the origin for auditing mirrors; none of these rows are
            # counted as independent canonical consensus votes.
            lineage_id = writer.lineage_id(
                f"external:{source}:{origin.lower()}"[:120],
                f"{spec.display_name}: {origin}"[:160],
                "Source-native; canonical episode identity not yet proven",
            )
            writer.add_source_title_ref(
                source_id=source_id,
                source_title_key=source_title_key,
                anchor_id=anchor,
                identity_method=f"amdb-{provider}-id",
            )
            evidence_id = writer.add_evidence_record(
                snapshot_id=snapshot_id,
                record_key=segment_key,
                lineage_key=f"external:{source}:{origin.lower()}"[:120],
                source_title_key=source_title_key,
                source_episode_key=source_episode_key,
                source_status="external-api-checkpoint",
                payload_sha256=hashlib.sha256(
                    json.dumps(item, sort_keys=True).encode()
                ).hexdigest(),
                normalization_status="source-only",
                normalization_reason="Source season/episode not proven as MAL/AniList episode",
                normalized_anchor_id=anchor,
                metadata={
                    "native_provider": provider,
                    "origin": origin,
                    "season": season,
                    "episode": episode,
                    "consensus_eligible": False,
                },
            )
            writer.add_evidence_segment(
                evidence_id,
                source_segment_id=segment_key,
                segment_type=kind,
                start_ms=start,
                end_ms=end,
            )
            writer.add_source_segment(
                source_id=source_id,
                lineage_id=lineage_id,
                source_title_key=source_title_key,
                source_episode_key=source_episode_key,
                source_segment_id=segment_key,
                segment_type=kind,
                start_ms=start,
                end_ms=end,
            )
            stats.evidence_segments += 1
            stats.source_only_segments += 1
            stats.anime_source_only_segments += 1
            detected_titles.add(anchor)
    stats.anime_titles_detected = len(detected_titles)
    return stats
