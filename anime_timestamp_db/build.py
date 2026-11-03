from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import zstandard as zstd

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.api_importer import import_api_checkpoint
from anime_timestamp_db.aniskip_importer import import_aniskip
from anime_timestamp_db.audit import audit_databases
from anime_timestamp_db.config import (
    ANIBRIDGE,
    ANIME_MAPPING_DB,
    ANISKIP,
    ANISKIP_API,
    ANIME_SKIP_API,
    BAHA,
    OPEN_ANIME_TIMESTAMPS,
    SKIPDB,
)
from anime_timestamp_db.consensus import rebuild_consensus
from anime_timestamp_db.database import DatabaseWriter
from anime_timestamp_db.distribution import (
    STORAGE_PROFILE,
    compact_evidence_database,
    compact_runtime_database,
)
from anime_timestamp_db.download import DownloadedSource, download_source
from anime_timestamp_db.episode_index import rebuild_episode_ids
from anime_timestamp_db.importers import import_baha, import_skipdb
from anime_timestamp_db.mapping_identity import (
    MappingAnchorIndex,
    decompress_mapping_database,
    mapping_database_metadata,
)
from anime_timestamp_db.normalization import merge_movie_episode_aliases
from anime_timestamp_db.open_anime_timestamps_importer import (
    import_open_anime_timestamps,
)
from anime_timestamp_db.schema import (
    DEFAULT_EVIDENCE_DB_NAME,
    DEFAULT_RUNTIME_DB_NAME,
    SCHEMA_VERSION,
)
from anime_timestamp_db.skipdb_mapping import SkipDBMappingIndex

BUILD_FORMAT_VERSION = 10


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
    api_checkpoint_dir: Path | None = None,
    allow_api_redistribution: bool = False,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(cache_dir or (output_dir / ".cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC).isoformat()
    if api_checkpoint_dir is not None and not allow_api_redistribution:
        raise ValueError(
            "API data redistribution has not been authorized: explicitly "
            "provide --allow-api-redistribution after verifying source terms"
        )
    api_sources = (("aniskip", ANISKIP_API), ("anime_skip", ANIME_SKIP_API))
    api_downloads: dict[str, DownloadedSource] = {}
    if api_checkpoint_dir is not None:
        directory = Path(api_checkpoint_dir)
        for source, spec in api_sources:
            path = directory / f"{source}.json.gz"
            if not path.is_file():
                raise FileNotFoundError(
                    f"API release import requested but checkpoint missing: {path}"
                )
            api_downloads[source] = DownloadedSource(
                key=spec.key,
                path=path,
                source_url=spec.url,
                final_url=spec.url,
                sha256=_sha256(path),
                size_bytes=path.stat().st_size,
                retrieved_at=generated_at,
                etag="",
                last_modified="",
                from_cache=False,
            )
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
    with (
        MappingAnchorIndex(mapping_path) as identities,
        DatabaseWriter(runtime_path, evidence_path, overwrite=True) as writer,
    ):
        writer.set_metadata("generated_at", generated_at)
        writer.set_metadata("api_sources_enabled", bool(api_downloads))
        writer.set_metadata(
            "api_redistribution_operator_authorized", bool(api_downloads)
        )
        writer.set_metadata("build_format_version", BUILD_FORMAT_VERSION)
        writer.set_metadata("consensus_algorithm", "weighted-median-v1")
        writer.set_metadata("consensus_tolerance_ms", consensus_tolerance_ms)
        writer.set_metadata("anime_mapping_db_sha256", mapping_download.sha256)
        writer.set_metadata(
            "anime_mapping_db_schema_version",
            mapping_metadata.get("schema_version", ""),
        )
        writer.set_metadata(
            "anime_mapping_db_anchor_schema_version",
            mapping_metadata.get("anchor_schema_version", ""),
        )
        writer.set_metadata(
            "anime_mapping_db_anchor_namespace",
            mapping_metadata.get("anchor_namespace", ""),
        )
        writer.set_metadata(
            "anime_mapping_db_anchor_entities",
            mapping_metadata.get("anchor_entities", "0"),
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
                "role": "stable-title-identity-resolver",
                "anchor_namespace": mapping_metadata.get("anchor_namespace", ""),
                "anchor_schema_version": mapping_metadata.get(
                    "anchor_schema_version", ""
                ),
                "anchor_entities": _metadata_int(mapping_metadata, "anchor_entities"),
                "provider_aliases_copied": False,
            },
        )
        writer.set_snapshot_record_count(
            mapping_snapshot,
            _metadata_int(mapping_metadata, "anchor_entities"),
        )

        aniskip_snapshot = writer.add_snapshot(
            ANISKIP,
            downloads[ANISKIP.key],
            metadata={
                "role": "primary-mal-native-timestamp-source",
                "title_identity": "MAL -> AMDB anchor",
                "public_sanitized_dataset": True,
                "explicit_redistribution_license_found": False,
                "user_id_imported": False,
            },
        )
        aniskip_stats = import_aniskip(
            downloads[ANISKIP.key].path,
            writer=writer,
            snapshot_id=aniskip_snapshot,
            identities=identities,
        )

        skip_snapshot = writer.add_snapshot(
            SKIPDB,
            downloads[SKIPDB.key],
            metadata={
                "role": "timestamp-source",
                "episode_normalization": (
                    "IMDb -> anime-mapping-db TVDB/TMDB -> AniBridge -> AMDB anchor"
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
                identities=identities,
            )

        oat_snapshot = writer.add_snapshot(
            OPEN_ANIME_TIMESTAMPS,
            downloads[OPEN_ANIME_TIMESTAMPS.key],
            metadata={
                "role": "anidb-native-timestamp-source-and-aggregator",
                "episode_normalization": (
                    "AniDB:R -> AniBridge -> AMDB anchor/provider numbering"
                ),
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
            identities=identities,
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

        api_stats: dict[str, dict[str, object]] = {}
        for source, spec in api_sources:
            if source not in api_downloads:
                continue
            download = api_downloads[source]
            snapshot_id = writer.add_snapshot(
                spec,
                download,
                metadata={
                    "role": "opt-in-live-api-checkpoint",
                    "checkpoint_schema_version": 1,
                    "source_native_title_id": (
                        "mal" if source == "aniskip" else "anilist"
                    ),
                    "operator_authorized_redistribution": True,
                    "explicit_upstream_dataset_license_found": False,
                    "independent_episode_mapping_required": source == "anime_skip",
                },
            )
            api_stats[spec.key] = import_api_checkpoint(
                download.path,
                source=source,
                writer=writer,
                snapshot_id=snapshot_id,
                identities=identities,
            ).as_dict()

        normalization_stats = merge_movie_episode_aliases(writer.conn)
        with SkipDBMappingIndex(mapping_path, anibridge) as skipdb_mappings:
            episode_index_stats = rebuild_episode_ids(
                writer.conn,
                skipdb_mappings,
                identities,
            )

        consensus_stats = rebuild_consensus(
            writer.conn,
            tolerance_ms=consensus_tolerance_ms,
        )
        identity_stats = identities.stats.as_dict()
        writer.set_metadata(
            "identity_lookup_stats", json.dumps(identity_stats, sort_keys=True)
        )
        writer.finalize()

    staging_audit = audit_databases(runtime_path, evidence_path)
    if not staging_audit["ok"]:
        raise RuntimeError(
            "Built staging database failed audit: "
            f"{json.dumps(staging_audit, sort_keys=True)}"
        )

    staging_sizes = {
        DEFAULT_RUNTIME_DB_NAME: runtime_path.stat().st_size,
        DEFAULT_EVIDENCE_DB_NAME: evidence_path.stat().st_size,
    }
    compact_runtime_path = output_dir / f".{DEFAULT_RUNTIME_DB_NAME}.compact"
    compact_evidence_path = output_dir / f".{DEFAULT_EVIDENCE_DB_NAME}.compact"
    compact_runtime_database(runtime_path, compact_runtime_path)
    compact_evidence_database(evidence_path, compact_evidence_path)
    distribution_audit = audit_databases(compact_runtime_path, compact_evidence_path)
    if not distribution_audit["ok"]:
        raise RuntimeError(
            "Compact distribution database failed audit: "
            f"{json.dumps(distribution_audit, sort_keys=True)}"
        )
    compact_runtime_path.replace(runtime_path)
    compact_evidence_path.replace(evidence_path)
    audit = distribution_audit

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
    if api_downloads:
        notices += (("ANIME_SKIP_API_NOTICE.md", None),)
    for name, output_name in notices:
        _copy_notice(name, output_dir, output_name=output_name)

    manifest: dict[str, Any] = {
        "project": "anime-timestamp-db",
        "schema_version": SCHEMA_VERSION,
        "build_format_version": BUILD_FORMAT_VERSION,
        "generated_at": generated_at,
        "identity": {
            "namespace": "amdb",
            "mapping_database_sha256": mapping_download.sha256,
            "mapping_database_schema_version": mapping_metadata.get(
                "schema_version", ""
            ),
            "anchor_schema_version": mapping_metadata.get("anchor_schema_version", ""),
            "anchor_entities": _metadata_int(mapping_metadata, "anchor_entities"),
            "provider_aliases_copied": False,
            "lookup_stats": identity_stats,
        },
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
            **api_stats,
            "aniskip": aniskip_stats.as_dict(),
            "skipdb": skip_stats.as_dict(),
            "open-anime-timestamps": oat_stats.as_dict(),
            "baha": baha_stats.as_dict(),
            "anibridge_mapping_entries": bridge_entry_count,
        },
        "api_crawler": {
            "enabled": bool(api_downloads),
            "operator_authorized_redistribution": bool(api_downloads),
            "sources": list(api_downloads),
        },
        "normalization": normalization_stats.as_dict(),
        "episode_index": episode_index_stats.as_dict(),
        "consensus": consensus_stats,
        "audit": audit,
        "storage": {
            "profile": STORAGE_PROFILE,
            "staging_audit_ok": bool(staging_audit["ok"]),
            "staging_size_bytes": staging_sizes,
            "distribution_size_bytes": {
                DEFAULT_RUNTIME_DB_NAME: runtime_path.stat().st_size,
                DEFAULT_EVIDENCE_DB_NAME: evidence_path.stat().st_size,
            },
        },
        "artifacts": {},
    }

    for source, spec in api_sources:
        if source not in api_downloads:
            continue
        manifest["sources"][spec.key] = {
            **_download_manifest(api_downloads[source]),
            "display_name": spec.display_name,
            "homepage_url": spec.homepage_url,
            "source_kind": spec.source_kind,
            "license_note": spec.license_note,
            "explicit_redistribution_license": False,
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
