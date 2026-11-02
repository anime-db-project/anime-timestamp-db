from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path

import zstandard as zstd

from anime_timestamp_db.database import DatabaseWriter


@dataclass(slots=True)
class MappingEnrichmentStats:
    mapping_schema_version: str = ""
    local_mal_titles: int = 0
    matched_mal_titles: int = 0
    enriched_titles: int = 0
    aliases_added: int = 0
    aliases_already_present: int = 0
    mapping_conflicts: int = 0
    local_conflicts: int = 0
    providers_added: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["providers_added"] = dict(sorted(self.providers_added.items()))
        return result


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _connect_readonly(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    conn = sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def decompress_mapping_database(source: Path, target: Path) -> Path:
    """Decompress a hash-addressed ``mappings.db.zst`` and validate SQLite."""

    source = Path(source)
    target = Path(target)
    if target.is_file():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.unlink(missing_ok=True)

    decompressor = zstd.ZstdDecompressor()
    try:
        with source.open("rb") as src, temporary.open("wb") as dst:
            decompressor.copy_stream(src, dst)
        with closing(_connect_readonly(temporary)) as conn:
            quick_check = conn.execute("PRAGMA quick_check").fetchone()
            if quick_check is None or str(quick_check[0]) != "ok":
                raise RuntimeError(
                    f"anime-mapping-db quick_check failed: {quick_check!r}"
                )
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

    return target


def mapping_database_metadata(path: Path) -> dict[str, str]:
    with closing(_connect_readonly(path)) as conn:
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"metadata", "nodes", "edges", "conflicts"}
        missing = sorted(required - tables)
        if missing:
            raise ValueError(
                "anime-mapping-db is missing required tables: " + ", ".join(missing)
            )
        metadata = {
            str(row[0]): str(row[1])
            for row in conn.execute("SELECT key, value FROM metadata ORDER BY key")
        }
        if metadata.get("database_role") != "runtime":
            raise ValueError("anime-mapping-db input is not a runtime mapping database")
        return metadata


def enrich_titles_from_mapping_db(
    path: Path,
    *,
    writer: DatabaseWriter,
    snapshot_id: int,
) -> MappingEnrichmentStats:
    """Attach conflict-free direct accepted aliases to existing MAL titles.

    This intentionally enriches title identity only. Provider episode numbering
    is never inferred from a title alias.
    """

    metadata = mapping_database_metadata(path)
    stats = MappingEnrichmentStats(
        mapping_schema_version=metadata.get("schema_version", "")
    )
    provider_counts: defaultdict[str, int] = defaultdict(int)

    local_titles = writer.conn.execute(
        """
        SELECT title_id, external_id
        FROM title_ids
        WHERE provider='mal'
        ORDER BY CAST(external_id AS INTEGER), external_id
        """
    ).fetchall()
    stats.local_mal_titles = len(local_titles)

    with closing(_connect_readonly(path)) as mappings:
        for title_id_raw, mal_id_raw in local_titles:
            title_id = int(title_id_raw)
            mal_id = str(mal_id_raw)
            source = mappings.execute(
                """
                SELECT id FROM nodes
                WHERE provider='mal' AND external_id=?
                """,
                (mal_id,),
            ).fetchone()
            if source is None:
                continue

            source_node = int(source[0])
            conflict_details: dict[str, list[str]] = {}
            for row in mappings.execute(
                """
                SELECT target_provider, candidate_ids_json
                FROM conflicts
                WHERE source_node=?
                ORDER BY target_provider
                """,
                (source_node,),
            ):
                provider = str(row[0]).strip().casefold()
                try:
                    candidates = json.loads(str(row[1]))
                except json.JSONDecodeError:
                    candidates = []
                conflict_details[provider] = sorted(
                    str(value) for value in candidates if str(value)
                )
            conflict_providers = set(conflict_details)
            stats.mapping_conflicts += len(conflict_providers)

            targets: defaultdict[str, set[str]] = defaultdict(set)
            rows = mappings.execute(
                """
                SELECT target.provider, target.external_id
                FROM edges AS edge
                JOIN nodes AS target
                  ON target.id = CASE
                      WHEN edge.a_node=? THEN edge.b_node
                      ELSE edge.a_node
                  END
                WHERE edge.status='accepted'
                  AND (edge.a_node=? OR edge.b_node=?)
                ORDER BY target.provider, target.external_id
                """,
                (source_node, source_node, source_node),
            )
            for row in rows:
                provider = str(row[0]).strip().casefold()
                external_id = str(row[1]).strip()
                if (
                    not provider
                    or not external_id
                    or provider == "mal"
                    or provider in conflict_providers
                ):
                    continue
                targets[provider].add(external_id)

            if not targets and not conflict_providers:
                continue
            stats.matched_mal_titles += 1

            accepted: dict[str, str] = {}
            skipped_mapping: dict[str, list[str]] = {}
            for provider, values in sorted(targets.items()):
                if len(values) != 1:
                    stats.mapping_conflicts += 1
                    skipped_mapping[provider] = sorted(values)
                    continue
                accepted[provider] = next(iter(values))

            added: dict[str, str] = {}
            existing: dict[str, str] = {}
            local_conflicts: dict[str, str] = {}
            for provider, external_id in accepted.items():
                row = writer.conn.execute(
                    """
                    SELECT title_id FROM title_ids
                    WHERE provider=? AND external_id=?
                    """,
                    (provider, external_id),
                ).fetchone()
                if row is not None:
                    if int(row[0]) == title_id:
                        stats.aliases_already_present += 1
                        existing[provider] = external_id
                    else:
                        stats.local_conflicts += 1
                        local_conflicts[provider] = external_id
                    continue

                writer.conn.execute(
                    """
                    INSERT INTO title_ids(provider, external_id, title_id)
                    VALUES (?, ?, ?)
                    """,
                    (provider, external_id, title_id),
                )
                stats.aliases_added += 1
                provider_counts[provider] += 1
                added[provider] = external_id

            if added:
                stats.enriched_titles += 1

            evidence_payload = {
                "mal": mal_id,
                "accepted": accepted,
                "added": added,
                "already_present": existing,
                "mapping_conflicts": {
                    provider: skipped_mapping.get(
                        provider, conflict_details.get(provider, [])
                    )
                    for provider in sorted(
                        conflict_providers | set(skipped_mapping)
                    )
                },
                "local_conflicts": local_conflicts,
            }
            if added or existing:
                normalization_status = "mapped"
                normalization_reason = "direct accepted anime-mapping-db title aliases"
            else:
                normalization_status = "ambiguous"
                normalization_reason = "all direct aliases were conflicted or suppressed"

            writer.add_evidence_record(
                snapshot_id=snapshot_id,
                record_key=f"anime-mapping-db:mal:{mal_id}",
                lineage_key="anime-mapping-db",
                source_title_key=mal_id,
                source_status="accepted-direct",
                payload_sha256=_canonical_hash(evidence_payload),
                normalization_status=normalization_status,
                normalization_reason=normalization_reason,
                normalized_provider="mal",
                normalized_id=mal_id,
                metadata=evidence_payload,
            )

    stats.providers_added = dict(provider_counts)
    writer.commit()
    return stats
