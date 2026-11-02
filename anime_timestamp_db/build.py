from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import zstandard as zstd

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.aniskip_importer import import_aniskip
from anime_timestamp_db.audit import audit_databases
from anime_timestamp_db.config import (
    ANIBRIDGE,
    ANIME_MAPPING_DB,
    ANISKIP,
    BAHA,
    OPEN_ANIME_TIMESTAMPS,
    SKIPDB,
)
from anime_timestamp_db.consensus import rebuild_consensus
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.download import DownloadedSource, download_source
from anime_timestamp_db.episode_index import rebuild_episode_ids
from anime_timestamp_db.importers import import_baha, import_skipdb
from anime_timestamp_db.open_anime_timestamps_importer import (
    import_open_anime_timestamps,
)
from anime_timestamp_db.skipdb_mapping import SkipDBMappingIndex
from anime_timestamp_db.mapping_enrichment import (
    decompress_mapping_database,
    enrich_titles_from_mapping_db,
    mapping_database_metadata,
)
from anime_timestamp_db.normalization import merge_movie_episode_aliases
from anime_timestamp_db.schema import (
    DEFAULT_EVIDENCE_DB_NAME,
    DEFAULT_RUNTIME_DB_NAME,
    SCHEMA_VERSION,
)

BUILD_FORMAT_VERSION = 6


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compress(source: Path, target: Path, *, level: int = 10) -> None:
    compressor = zstd.ZstdCompressor(level=level, threads=-1)
    with Path(source).open("rb") as src, Path(target).open("wb") as dst:
        compressor.copy_stream(src, dst)


def _copy_notice(
    name: str, output_dir: Path, *, output_name: str | None = None
) -> None:
    root = Path(__file__).resolve().parent.parent
    source = root / name
    if source.is_file():
        shutil.copy2(source, output_dir / (output_name or Path(name).name))


def _download_manifest(download: DownloadedSource) -> dict[str, object]:
    return {
        "source_url": download.source_url,
        "final_url": download.final_url,
        "sha256": download.sha256,
        "size_bytes": download.size_bytes,
        "retrieved_at": download.retrieved_at,
        "etag": download.etag,
        "last_modified": download.last_modified,
        "from_cache": download.from_cache,
    }


def _metadata_int(metadata: dict[str, str], key: str) -> int:
    try:
        return max(0, int(metadata.get(key, "0")))
    except (TypeError, ValueError):
        return 0


def build_database(
    output_dir: Path,
    *,
    cache_dir: Path | None = None,
    force_download: bool = False,
    consensus_tolerance_ms: int = 5000,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(cache_dir or (output_dir / ".cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC).isoformat()
    specs = (
        ANIBRIDGE,
        ANIME_MAPPING_DB,
        ANISKIP,
        SKIPDB,
        OPEN_ANIME_TIMESTAMPS,
        BAHA,
    )
    downloads = {
        spec.key: download_source(spec, cache_dir, force=force_download)
        for spec in specs
    }

    mapping_download = downloads[ANIME_MAPPING_DB.key]
    mapping_path = decompress_mapping_database(
        mapping_download.path,
        cache_dir / f"anime-mapping-db-{mapping_download.sha256}.db",
    )
    mapping_metadata = mapping_database_metadata(mapping_path)

    runtime_path = output_dir / DEFAULT_RUNTIME_DB_NAME
    evidence_path = output_dir / DEFAULT_EVIDENCE_DB_NAME
    with DatabaseWriter(runtime_path, evidence_path, overwrite=True) as writer:
        writer.set_metadata("generated_at", generated_at)
        writer.set_metadata("build_format_version", BUILD_FORMAT_VERSION)
        writer.set_metadata("consensus_algorithm", "weighted-median-v1")
        writer.set_metadata("consensus_tolerance_ms", consensus_tolerance_ms)
        writer.set_metadata("anime_mapping_db_sha256", mapping_download.sha256)
        writer.set_metadata(
            "anime_mapping_db_schema_version",
            mapping_metadata.get("schema_version", ""),
        )

        anibridge = AniBridgeIndex.from_file(downloads[ANIBRIDGE.key].path)
        bridge_snapshot = writer.add_snapshot(
            ANIBRIDGE,
            downloads[ANIBRIDGE.key],
            upstream_version=str(anibridge.meta.get("version") or "v3"),
            metadata={"role": "episode-normalization", "payload_meta": anibridge.meta},
        )
        bridge_entry_count = max(
            0,
            len(anibridge.payload) - (1 if "$meta" in anibridge.payload else 0),
        )
        writer.set_snapshot_record_count(bridge_snapshot, bridge_entry_count)

        mapping_snapshot = writer.add_snapshot(
            ANIME_MAPPING_DB,
            mapping_download,
            upstream_version=mapping_metadata.get("built_at", ""),
            metadata={
                "role": "direct-accepted-title-id-enrichment",
                "mapping_database_metadata": mapping_metadata,
                "episode_numbering_inferred": False,
            },
        )
        writer.set_snapshot_record_count(
            mapping_snapshot,
            _metadata_int(mapping_metadata, "accepted_edges"),
        )

        aniskip_snapshot = writer.add_snapshot(
            ANISKIP,
            downloads[ANISKIP.key],
            metadata={
                "role": "primary-mal-native-timestamp-source",
                "public_sanitized_dataset": True,
                "explicit_redistribution_license_found": False,
                "user_id_imported": False,
            },
        )
        aniskip_stats = import_aniskip(
            downloads[ANISKIP.key].path,
            writer=writer,
            snapshot_id=aniskip_snapshot,
        )

        skip_snapshot = writer.add_snapshot(
            SKIPDB,
            downloads[SKIPDB.key],
            metadata={
                "role": "timestamp-source",
                "episode_normalization": (
                    "IMDb -> anime-mapping-db TVDB/TMDB -> AniBridge"
                ),
                "season_offset_inference": True,
            },
        )
        with SkipDBMappingIndex(mapping_path, anibridge) as skipdb_mappings:
            skip_stats = import_skipdb(
                downloads[SKIPDB.key].path,
                writer=writer,
                snapshot_id=skip_snapshot,
                mappings=skipdb_mappings,
            )

        oat_snapshot = writer.add_snapshot(
            OPEN_ANIME_TIMESTAMPS,
            downloads[OPEN_ANIME_TIMESTAMPS.key],
            metadata={
                "role": "anidb-native-timestamp-source-and-aggregator",
                "episode_normalization": "AniDB:R -> AniBridge -> MAL/AniList/AniDB",
                "field_level_lineage_available": False,
                "multi_source_records_consensus_eligible": False,
                "explicit_redistribution_license_found": False,
            },
        )
        oat_stats = import_open_anime_timestamps(
            downloads[OPEN_ANIME_TIMESTAMPS.key].path,
            writer=writer,
            snapshot_id=oat_snapshot,
            anibridge=anibridge,
        )

        baha_snapshot = writer.add_snapshot(
            BAHA,
            downloads[BAHA.key],
            metadata={"role": "timestamp-source", "identity": "upstream-videoSn-only"},
        )
        baha_stats = import_baha(
            downloads[BAHA.key].path,
            writer=writer,
            snapshot_id=baha_snapshot,
        )

        normalization_stats = merge_movie_episode_aliases(writer.conn)
        enrichment_stats = enrich_titles_from_mapping_db(
            mapping_path,
            writer=writer,
            snapshot_id=mapping_snapshot,
        )
        with SkipDBMappingIndex(mapping_path, anibridge) as skipdb_mappings:
            episode_index_stats = rebuild_episode_ids(writer.conn, skipdb_mappings)

        consensus_stats = rebuild_consensus(
            writer.conn,
            tolerance_ms=consensus_tolerance_ms,
        )
        writer.finalize()

    audit = audit_databases(runtime_path, evidence_path)
    if not audit["ok"]:
        raise RuntimeError(
            f"Built database failed audit: {json.dumps(audit, sort_keys=True)}"
        )

    runtime_zst = output_dir / f"{DEFAULT_RUNTIME_DB_NAME}.zst"
    evidence_zst = output_dir / f"{DEFAULT_EVIDENCE_DB_NAME}.zst"
    _compress(runtime_path, runtime_zst)
    _compress(evidence_path, evidence_zst)

    notices = (
        ("DATA_LICENSE.md", None),
        ("THIRD_PARTY_NOTICES.md", None),
        ("ANISKIP_PUBLIC_DATA_NOTICE.md", None),
        ("OPEN_ANIME_TIMESTAMPS_NOTICE.md", None),
        ("licenses/SKIPDB_DATA_LICENSE.txt", None),
        ("licenses/BAHA_LICENSE.txt", None),
        ("licenses/ANIBRIDGE_LICENSE.txt", None),
        ("licenses/anime-mapping-db/DATA_LICENSE.md", "MAPPING_DB_DATA_LICENSE.md"),
        (
            "licenses/anime-mapping-db/THIRD_PARTY_NOTICES.md",
            "MAPPING_DB_THIRD_PARTY_NOTICES.md",
        ),
    )
    for name, output_name in notices:
        _copy_notice(name, output_dir, output_name=output_name)

    manifest: dict[str, Any] = {
        "project": "anime-timestamp-db",
        "schema_version": SCHEMA_VERSION,
        "build_format_version": BUILD_FORMAT_VERSION,
        "generated_at": generated_at,
        "sources": {
            spec.key: {
                **_download_manifest(downloads[spec.key]),
                "display_name": spec.display_name,
                "homepage_url": spec.homepage_url,
                "source_kind": spec.source_kind,
                "license_note": spec.license_note,
                "explicit_redistribution_license": spec.explicit_redistribution_license,
            }
            for spec in specs
        },
        "imports": {
            "aniskip": aniskip_stats.as_dict(),
            "skipdb": skip_stats.as_dict(),
            "open-anime-timestamps": oat_stats.as_dict(),
            "baha": baha_stats.as_dict(),
            "anibridge_mapping_entries": bridge_entry_count,
        },
        "normalization": normalization_stats.as_dict(),
        "title_enrichment": enrichment_stats.as_dict(),
        "episode_index": episode_index_stats.as_dict(),
        "consensus": consensus_stats,
        "audit": audit,
        "artifacts": {},
    }

    for path in (runtime_path, runtime_zst, evidence_path, evidence_zst):
        manifest["artifacts"][path.name] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "utf-8",
    )

    checksum_paths = [
        runtime_path,
        runtime_zst,
        evidence_path,
        evidence_zst,
        manifest_path,
    ]
    for source_name, output_name in notices:
        name = output_name or Path(source_name).name
        path = output_dir / name
        if path.is_file():
            checksum_paths.append(path)
    (output_dir / "SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in checksum_paths),
        "utf-8",
    )
    return manifest
