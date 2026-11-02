from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import zstandard as zstd

from anime_timestamp_db.anibridge import AniBridgeIndex
from anime_timestamp_db.audit import audit_databases
from anime_timestamp_db.build import build_database as _build_database
from anime_timestamp_db.config import ANIBRIDGE
from anime_timestamp_db.download import download_source
from anime_timestamp_db.episode_index import rebuild_episode_ids
from anime_timestamp_db.schema import DEFAULT_EVIDENCE_DB_NAME, DEFAULT_RUNTIME_DB_NAME


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


def _rewrite_checksums(output_dir: Path) -> None:
    names = (
        DEFAULT_RUNTIME_DB_NAME,
        f"{DEFAULT_RUNTIME_DB_NAME}.zst",
        DEFAULT_EVIDENCE_DB_NAME,
        f"{DEFAULT_EVIDENCE_DB_NAME}.zst",
        "manifest.json",
        "DATA_LICENSE.md",
        "THIRD_PARTY_NOTICES.md",
        "ANISKIP_PUBLIC_DATA_NOTICE.md",
        "SKIPDB_DATA_LICENSE.txt",
        "BAHA_LICENSE.txt",
        "ANIBRIDGE_LICENSE.txt",
    )
    paths = [output_dir / name for name in names if (output_dir / name).is_file()]
    (output_dir / "SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in paths),
        "utf-8",
    )


def build_database(
    output_dir: Path,
    *,
    cache_dir: Path | None = None,
    force_download: bool = False,
    consensus_tolerance_ms: int = 5000,
) -> dict[str, Any]:
    """Run the base builder and add safe cross-provider episode indexes."""

    output_dir = Path(output_dir)
    resolved_cache = Path(cache_dir or (output_dir / ".cache"))
    manifest = _build_database(
        output_dir,
        cache_dir=resolved_cache,
        force_download=force_download,
        consensus_tolerance_ms=consensus_tolerance_ms,
    )

    bridge_download = download_source(ANIBRIDGE, resolved_cache)
    mappings = AniBridgeIndex.from_file(bridge_download.path)
    runtime_path = output_dir / DEFAULT_RUNTIME_DB_NAME
    evidence_path = output_dir / DEFAULT_EVIDENCE_DB_NAME

    conn = sqlite3.connect(runtime_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        episode_index = rebuild_episode_ids(conn, mappings)
        conn.execute("ANALYZE")
        conn.execute("PRAGMA optimize")
        conn.commit()
    finally:
        conn.close()

    audit = audit_databases(runtime_path, evidence_path)
    if not audit["ok"]:
        raise RuntimeError(
            "Post-index database failed audit: "
            + json.dumps(audit, ensure_ascii=False, sort_keys=True)
        )

    runtime_zst = output_dir / f"{DEFAULT_RUNTIME_DB_NAME}.zst"
    _compress(runtime_path, runtime_zst)

    manifest["episode_index"] = episode_index.as_dict()
    manifest["audit"] = audit
    for name in (
        DEFAULT_RUNTIME_DB_NAME,
        f"{DEFAULT_RUNTIME_DB_NAME}.zst",
        DEFAULT_EVIDENCE_DB_NAME,
        f"{DEFAULT_EVIDENCE_DB_NAME}.zst",
    ):
        path = output_dir / name
        manifest.setdefault("artifacts", {})[name] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "utf-8",
    )
    _rewrite_checksums(output_dir)
    return manifest
