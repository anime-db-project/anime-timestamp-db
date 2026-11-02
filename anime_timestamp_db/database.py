from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from anime_timestamp_db.config import SourceSpec
from anime_timestamp_db.schema import EVIDENCE_SCHEMA, RUNTIME_SCHEMA, SCHEMA_VERSION


class IdentityConflict(RuntimeError):
    pass


def _prepare_path(path: Path, *, overwrite: bool) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not overwrite:
            raise FileExistsError(path)
        path.unlink()
    return path


def _connect_build(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute("PRAGMA cache_size=-65536")
    return conn


def _initialize_database(
    path: Path,
    *,
    role: str,
    schema: str,
    overwrite: bool,
) -> Path:
    path = _prepare_path(Path(path), overwrite=overwrite)
    with closing(_connect_build(path)) as conn:
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.executescript(schema)
        conn.executemany(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            (
                ("schema_version", str(SCHEMA_VERSION)),
                ("database_role", role),
                ("project", "anime-timestamp-db"),
            ),
        )
        conn.commit()
    return path


def create_runtime_database(path: Path, *, overwrite: bool = False) -> Path:
    return _initialize_database(
        Path(path), role="runtime", schema=RUNTIME_SCHEMA, overwrite=overwrite
    )


def create_evidence_database(path: Path, *, overwrite: bool = False) -> Path:
    return _initialize_database(
        Path(path), role="evidence", schema=EVIDENCE_SCHEMA, overwrite=overwrite
    )


def connect_readonly(path: Path) -> sqlite3.Connection:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row[0]): str(row[1])
        for row in conn.execute("SELECT key, value FROM metadata ORDER BY key")
    }


def inspect_database(path: Path) -> dict[str, Any]:
    with closing(connect_readonly(path)) as conn:
        metadata = _metadata(conn)
        role = metadata.get("database_role", "")
        schema_version = metadata.get("schema_version", "")
        if schema_version != str(SCHEMA_VERSION):
            raise ValueError(
                f"Unsupported schema version {schema_version!r}; expected {SCHEMA_VERSION}"
            )
        tables = {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if role == "runtime":
            wanted = (
                "sources",
                "lineages",
                "titles",
                "title_ids",
                "episodes",
                "episode_refs",
                "segments",
                "source_segments",
                "consensus_segments",
                "consensus_members",
            )
        elif role == "evidence":
            wanted = ("source_snapshots", "records", "record_segments")
        else:
            raise ValueError(f"Unknown database role {role!r}")
        counts: dict[str, int] = {}
        for table in wanted:
            if table not in tables:
                raise ValueError(f"Missing required table {table!r}")
            counts[table] = int(
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
        return {"path": str(Path(path)), "metadata": metadata, "counts": counts}


def inspect_database_json(path: Path) -> str:
    return json.dumps(
        inspect_database(path), ensure_ascii=False, indent=2, sort_keys=True
    )


class DatabaseWriter:
    def __init__(
        self, runtime_path: Path, evidence_path: Path, *, overwrite: bool = True
    ) -> None:
        create_runtime_database(runtime_path, overwrite=overwrite)
        create_evidence_database(evidence_path, overwrite=overwrite)
        self.runtime_path = Path(runtime_path)
        self.evidence_path = Path(evidence_path)
        self.conn = _connect_build(self.runtime_path)
        self.evidence = _connect_build(self.evidence_path)
        self._source_ids: dict[str, int] = {}
        self._lineage_ids: dict[str, int] = {}

    def close(self) -> None:
        self.conn.commit()
        self.evidence.commit()
        self.conn.close()
        self.evidence.close()

    def __enter__(self) -> "DatabaseWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.conn.commit()
            self.evidence.commit()
        else:
            self.conn.rollback()
            self.evidence.rollback()
        self.conn.close()
        self.evidence.close()

    def set_metadata(self, key: str, value: object) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES(?, ?)",
            (str(key), str(value)),
        )
        self.evidence.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES(?, ?)",
            (str(key), str(value)),
        )

    def source_id(self, spec: SourceSpec) -> int:
        cached = self._source_ids.get(spec.key)
        if cached is not None:
            return cached
        self.conn.execute(
            """
            INSERT OR IGNORE INTO sources(
                source_key, display_name, homepage_url, source_kind, license_note
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                spec.key,
                spec.display_name,
                spec.homepage_url,
                spec.source_kind,
                spec.license_note,
            ),
        )
        row = self.conn.execute(
            "SELECT id FROM sources WHERE source_key=?", (spec.key,)
        ).fetchone()
        assert row is not None
        source_id = int(row[0])
        self._source_ids[spec.key] = source_id
        return source_id

    def lineage_id(self, key: str, display_name: str, description: str = "") -> int:
        normalized = str(key).strip().casefold()
        cached = self._lineage_ids.get(normalized)
        if cached is not None:
            return cached
        self.conn.execute(
            """
            INSERT OR IGNORE INTO lineages(lineage_key, display_name, description)
            VALUES (?, ?, ?)
            """,
            (normalized, display_name, description),
        )
        row = self.conn.execute(
            "SELECT id FROM lineages WHERE lineage_key=?", (normalized,)
        ).fetchone()
        assert row is not None
        lineage_id = int(row[0])
        self._lineage_ids[normalized] = lineage_id
        return lineage_id

    def add_snapshot(
        self,
        spec: SourceSpec,
        download: Any,
        *,
        upstream_version: str = "",
        metadata: dict[str, object] | None = None,
    ) -> int:
        cursor = self.evidence.execute(
            """
            INSERT INTO source_snapshots(
                source_key, source_kind, source_url, final_url, upstream_version,
                sha256, size_bytes, retrieved_at, etag, last_modified,
                license_note, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                spec.key,
                spec.source_kind,
                download.source_url,
                download.final_url,
                upstream_version,
                download.sha256,
                download.size_bytes,
                download.retrieved_at,
                download.etag,
                download.last_modified,
                spec.license_note,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)

    def set_snapshot_record_count(self, snapshot_id: int, count: int) -> None:
        self.evidence.execute(
            "UPDATE source_snapshots SET record_count=? WHERE id=?",
            (count, snapshot_id),
        )

    def add_evidence_record(
        self,
        *,
        snapshot_id: int,
        record_key: str,
        lineage_key: str,
        source_title_key: str = "",
        source_episode_key: str = "",
        source_status: str = "",
        quality_score: float | None = None,
        votes_up: int = 0,
        votes_down: int = 0,
        payload_sha256: str = "",
        normalization_status: str = "unprocessed",
        normalization_reason: str = "",
        normalized_provider: str = "",
        normalized_id: str = "",
        normalized_episode_key: str = "",
        metadata: dict[str, object] | None = None,
    ) -> int:
        cursor = self.evidence.execute(
            """
            INSERT INTO records(
                snapshot_id, record_key, lineage_key, source_title_key,
                source_episode_key, source_status, quality_score, votes_up,
                votes_down, payload_sha256, normalization_status,
                normalization_reason, normalized_provider, normalized_id,
                normalized_episode_key, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                record_key,
                lineage_key,
                source_title_key,
                source_episode_key,
                source_status,
                quality_score,
                max(0, int(votes_up)),
                max(0, int(votes_down)),
                payload_sha256,
                normalization_status,
                normalization_reason,
                normalized_provider,
                normalized_id,
                normalized_episode_key,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)

    def add_evidence_segment(
        self,
        record_id: int,
        *,
        source_segment_id: str,
        segment_type: str,
        start_ms: int,
        end_ms: int,
        media_duration_ms: int | None = None,
    ) -> None:
        self.evidence.execute(
            """
            INSERT INTO record_segments(
                record_id, source_segment_id, segment_type, start_ms, end_ms,
                media_duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                source_segment_id,
                segment_type,
                int(start_ms),
                int(end_ms),
                media_duration_ms,
            ),
        )

    def get_or_create_title(
        self,
        ids: dict[str, str],
        *,
        display_title: str = "",
    ) -> int:
        cleaned = {
            str(provider).strip().casefold(): str(external_id).strip()
            for provider, external_id in ids.items()
            if str(provider).strip() and str(external_id).strip()
        }
        if not cleaned:
            raise ValueError("At least one title ID is required")

        placeholders = ",".join("(?, ?)" for _ in cleaned)
        params: list[str] = []
        for provider, external_id in cleaned.items():
            params.extend((provider, external_id))
        existing = {
            int(row[0])
            for row in self.conn.execute(
                f"""
                SELECT title_id FROM title_ids
                WHERE (provider, external_id) IN ({placeholders})
                """,
                params,
            )
        }
        if len(existing) > 1:
            raise IdentityConflict(
                f"IDs resolve to multiple existing titles: {cleaned}"
            )

        if existing:
            title_id = next(iter(existing))
        else:
            priority = ("mal", "anilist", "anidb")
            canonical_provider = next(
                (p for p in priority if p in cleaned), sorted(cleaned)[0]
            )
            canonical_id = cleaned[canonical_provider]
            cursor = self.conn.execute(
                """
                INSERT INTO titles(canonical_provider, canonical_id, display_title)
                VALUES (?, ?, ?)
                """,
                (canonical_provider, canonical_id, display_title),
            )
            assert cursor.lastrowid is not None
            title_id = int(cursor.lastrowid)

        for provider, external_id in cleaned.items():
            row = self.conn.execute(
                "SELECT title_id FROM title_ids WHERE provider=? AND external_id=?",
                (provider, external_id),
            ).fetchone()
            if row is not None and int(row[0]) != title_id:
                raise IdentityConflict(
                    f"{provider}:{external_id} already belongs to title {row[0]}"
                )
            self.conn.execute(
                "INSERT OR IGNORE INTO title_ids(provider, external_id, title_id) VALUES (?, ?, ?)",
                (provider, external_id, title_id),
            )
        if display_title:
            self.conn.execute(
                "UPDATE titles SET display_title=? WHERE id=? AND display_title=''",
                (display_title, title_id),
            )
        return title_id

    def get_or_create_episode(
        self,
        title_id: int,
        *,
        episode_key: str,
        episode_number: int | float | None,
        is_special: bool = False,
        duration_ms: int | None = None,
    ) -> int:
        row = self.conn.execute(
            "SELECT id, duration_ms FROM episodes WHERE title_id=? AND episode_key=?",
            (title_id, episode_key),
        ).fetchone()
        if row is not None:
            episode_id = int(row[0])
            if row[1] is None and duration_ms is not None:
                self.conn.execute(
                    "UPDATE episodes SET duration_ms=? WHERE id=?",
                    (duration_ms, episode_id),
                )
            return episode_id
        cursor = self.conn.execute(
            """
            INSERT INTO episodes(
                title_id, episode_key, episode_number_text, episode_number,
                is_special, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                title_id,
                episode_key,
                "" if episode_number is None else str(episode_number),
                episode_number,
                int(is_special),
                duration_ms,
            ),
        )
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)

    def add_episode_ref(
        self,
        source_id: int,
        *,
        source_title_key: str,
        source_episode_key: str,
        episode_id: int,
        source_episode_number_text: str = "",
    ) -> None:
        row = self.conn.execute(
            """
            SELECT episode_id FROM episode_refs
            WHERE source_id=? AND source_title_key=? AND source_episode_key=?
            """,
            (source_id, source_title_key, source_episode_key),
        ).fetchone()
        if row is not None and int(row[0]) != episode_id:
            raise IdentityConflict(
                "source episode reference resolves to multiple normalized episodes: "
                f"{source_id}:{source_title_key}:{source_episode_key}"
            )
        self.conn.execute(
            """
            INSERT OR IGNORE INTO episode_refs(
                source_id, source_title_key, source_episode_key, episode_id,
                source_episode_number_text
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source_title_key,
                source_episode_key,
                episode_id,
                source_episode_number_text,
            ),
        )

    def add_episode_id(
        self,
        *,
        episode_id: int,
        provider: str,
        title_external_id: str,
        episode_number: int,
        scope: str = "",
    ) -> None:
        normalized_provider = str(provider).strip().casefold()
        normalized_id = str(title_external_id).strip()
        normalized_scope = str(scope or "").strip().upper()
        number_text = str(int(episode_number))
        title_match = self.conn.execute(
            """
            SELECT 1
            FROM episodes ep
            JOIN title_ids tid ON tid.title_id=ep.title_id
            WHERE ep.id=? AND tid.provider=? AND tid.external_id=?
            """,
            (episode_id, normalized_provider, normalized_id),
        ).fetchone()
        if title_match is None:
            raise IdentityConflict(
                f"episode {episode_id} does not belong to "
                f"{normalized_provider}:{normalized_id}"
            )
        row = self.conn.execute(
            """
            SELECT episode_id FROM episode_ids
            WHERE provider=? AND title_external_id=? AND scope=?
              AND episode_number_text=?
            """,
            (normalized_provider, normalized_id, normalized_scope, number_text),
        ).fetchone()
        if row is not None and int(row[0]) != episode_id:
            raise IdentityConflict(
                "provider episode identity resolves to multiple normalized episodes: "
                f"{normalized_provider}:{normalized_id}:{normalized_scope}:{number_text}"
            )
        self.conn.execute(
            """
            INSERT OR IGNORE INTO episode_ids(
                provider, title_external_id, scope, episode_number_text, episode_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalized_provider,
                normalized_id,
                normalized_scope,
                number_text,
                episode_id,
            ),
        )

    def add_segment(
        self,
        *,
        episode_id: int,
        source_id: int,
        lineage_id: int,
        source_segment_id: str,
        segment_type: str,
        start_ms: int,
        end_ms: int,
        media_duration_ms: int | None = None,
        quality_score: float | None = None,
        mapping_method: str = "native",
        mapping_confidence: float = 1.0,
        consensus_eligible: bool = True,
        votes_up: int = 0,
        votes_down: int = 0,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO segments(
                episode_id, source_id, lineage_id, source_segment_id,
                segment_type, start_ms, end_ms, media_duration_ms,
                quality_score, mapping_method, mapping_confidence,
                consensus_eligible, votes_up, votes_down
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode_id,
                source_id,
                lineage_id,
                source_segment_id,
                segment_type,
                start_ms,
                end_ms,
                media_duration_ms,
                quality_score,
                str(mapping_method),
                max(0.0, min(1.0, float(mapping_confidence))),
                int(bool(consensus_eligible)),
                max(0, int(votes_up)),
                max(0, int(votes_down)),
            ),
        )

    def add_source_segment(
        self,
        *,
        source_id: int,
        lineage_id: int,
        source_title_key: str,
        source_episode_key: str,
        source_segment_id: str,
        segment_type: str,
        start_ms: int,
        end_ms: int,
        media_duration_ms: int | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO source_segments(
                source_id, lineage_id, source_title_key, source_episode_key,
                source_segment_id, segment_type, start_ms, end_ms,
                media_duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                lineage_id,
                source_title_key,
                source_episode_key,
                source_segment_id,
                segment_type,
                start_ms,
                end_ms,
                media_duration_ms,
            ),
        )

    def commit(self) -> None:
        self.conn.commit()
        self.evidence.commit()

    def finalize(self) -> None:
        self.conn.commit()
        self.evidence.commit()
        for conn in (self.conn, self.evidence):
            conn.execute("ANALYZE")
            conn.execute("PRAGMA optimize")
            conn.commit()
            conn.execute("VACUUM")
            conn.commit()


def count_by(
    conn: sqlite3.Connection, query: str, params: Iterable[object] = ()
) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in conn.execute(query, tuple(params))}
