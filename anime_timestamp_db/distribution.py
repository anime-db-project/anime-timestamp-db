from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from anime_timestamp_db.schema import SCHEMA_VERSION

STORAGE_PROFILE = "compact-v1"

_RUNTIME_TABLES = (
    "metadata",
    "sources",
    "lineages",
    "titles",
    "episodes",
    "episode_ids",
    "episode_refs",
    "segments",
    "source_segments",
    "consensus_segments",
    "consensus_members",
)

_EVIDENCE_DICTIONARIES = (
    ("lineage_values", "lineage_key"),
    ("source_title_values", "source_title_key"),
    ("source_episode_values", "source_episode_key"),
    ("source_status_values", "source_status"),
    ("normalization_status_values", "normalization_status"),
    ("normalization_reason_values", "normalization_reason"),
    ("normalized_episode_values", "normalized_episode_key"),
    ("metadata_values", "metadata_json"),
)


def _configure_build(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def _verify(path: Path) -> None:
    with closing(sqlite3.connect(path, timeout=30.0)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed for {path}: {integrity}")
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise RuntimeError(
                f"SQLite foreign key check failed for {path}: {foreign_keys[:5]}"
            )


def _columns(conn: sqlite3.Connection, table: str) -> str:
    names = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
    if not names:
        raise RuntimeError(f"Could not inspect columns for {table!r}")
    return ", ".join(names)


def compact_runtime_database(source: Path, destination: Path) -> None:
    """Materialize a read-only distribution layout for ``timestamps.db``.

    The build database intentionally carries uniqueness constraints and reverse
    indexes used while normalizing and merging records.  The published database
    is immutable, so those structures provide no integrity benefit at runtime.
    This layout preserves every public table and column while keeping only the
    indexes used by resolver queries.
    """

    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        raise ValueError("runtime distribution destination must differ from source")
    destination.unlink(missing_ok=True)

    with closing(sqlite3.connect(destination, timeout=60.0)) as conn:
        _configure_build(conn)
        conn.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE sources (
                id INTEGER PRIMARY KEY,
                source_key TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                homepage_url TEXT NOT NULL DEFAULT '',
                source_kind TEXT NOT NULL DEFAULT 'dataset',
                license_note TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE lineages (
                id INTEGER PRIMARY KEY,
                lineage_key TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE titles (
                anchor_id INTEGER PRIMARY KEY CHECK(anchor_id > 0),
                display_title TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE episodes (
                id INTEGER PRIMARY KEY,
                anchor_id INTEGER NOT NULL REFERENCES titles(anchor_id) ON DELETE CASCADE,
                episode_key TEXT NOT NULL,
                episode_number_text TEXT NOT NULL DEFAULT '',
                episode_number REAL,
                is_special INTEGER NOT NULL DEFAULT 0 CHECK(is_special IN (0, 1)),
                duration_ms INTEGER CHECK(duration_ms IS NULL OR duration_ms > 0),
                UNIQUE(anchor_id, episode_key)
            );

            CREATE INDEX episodes_anchor_idx
                ON episodes(anchor_id, episode_number, episode_key);

            CREATE TABLE episode_ids (
                anchor_id INTEGER NOT NULL REFERENCES titles(anchor_id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT '',
                episode_number_text TEXT NOT NULL,
                episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
                PRIMARY KEY(anchor_id, provider, scope, episode_number_text)
            ) WITHOUT ROWID;

            CREATE TABLE episode_refs (
                source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                source_title_key TEXT NOT NULL DEFAULT '',
                source_episode_key TEXT NOT NULL,
                episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
                source_episode_number_text TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(source_id, source_title_key, source_episode_key)
            ) WITHOUT ROWID;

            CREATE TABLE segments (
                id INTEGER PRIMARY KEY,
                episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
                source_id INTEGER NOT NULL REFERENCES sources(id),
                lineage_id INTEGER NOT NULL REFERENCES lineages(id),
                source_segment_id TEXT NOT NULL,
                segment_type TEXT NOT NULL,
                start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
                end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
                media_duration_ms INTEGER CHECK(media_duration_ms IS NULL OR media_duration_ms > 0),
                quality_score REAL,
                mapping_method TEXT NOT NULL DEFAULT 'native',
                mapping_confidence REAL NOT NULL DEFAULT 1.0
                    CHECK(mapping_confidence >= 0.0 AND mapping_confidence <= 1.0),
                consensus_eligible INTEGER NOT NULL DEFAULT 1
                    CHECK(consensus_eligible IN (0, 1)),
                votes_up INTEGER NOT NULL DEFAULT 0 CHECK(votes_up >= 0),
                votes_down INTEGER NOT NULL DEFAULT 0 CHECK(votes_down >= 0)
            );

            CREATE INDEX segments_episode_idx
                ON segments(episode_id, segment_type, start_ms, end_ms);

            CREATE TABLE source_segments (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                lineage_id INTEGER NOT NULL REFERENCES lineages(id),
                source_title_key TEXT NOT NULL DEFAULT '',
                source_episode_key TEXT NOT NULL,
                source_segment_id TEXT NOT NULL,
                segment_type TEXT NOT NULL,
                start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
                end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
                media_duration_ms INTEGER CHECK(media_duration_ms IS NULL OR media_duration_ms > 0)
            );

            CREATE INDEX source_segments_lookup_idx
                ON source_segments(
                    source_id, source_title_key, source_episode_key, segment_type
                );

            CREATE TABLE consensus_segments (
                id INTEGER PRIMARY KEY,
                episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
                segment_type TEXT NOT NULL,
                cluster_index INTEGER NOT NULL,
                start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
                end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
                media_duration_ms INTEGER CHECK(media_duration_ms IS NULL OR media_duration_ms > 0),
                member_count INTEGER NOT NULL CHECK(member_count > 0),
                source_count INTEGER NOT NULL CHECK(source_count > 0),
                lineage_count INTEGER NOT NULL CHECK(lineage_count > 0),
                confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
                algorithm TEXT NOT NULL,
                tolerance_ms INTEGER NOT NULL CHECK(tolerance_ms >= 0)
            );

            CREATE INDEX consensus_episode_idx
                ON consensus_segments(episode_id, segment_type);

            CREATE TABLE consensus_members (
                consensus_id INTEGER NOT NULL REFERENCES consensus_segments(id) ON DELETE CASCADE,
                segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
                PRIMARY KEY(consensus_id, segment_id)
            ) WITHOUT ROWID;
            """
        )
        conn.execute("ATTACH DATABASE ? AS source_db", (source.resolve().as_posix(),))
        try:
            for table in _RUNTIME_TABLES:
                packed = _columns(conn, table)
                conn.execute(
                    f"INSERT INTO {table}({packed}) SELECT {packed} FROM source_db.{table}"
                )
            source_counts = {
                table: int(
                    conn.execute(f"SELECT COUNT(*) FROM source_db.{table}").fetchone()[
                        0
                    ]
                )
                for table in _RUNTIME_TABLES[1:]
            }
            compact_counts = {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in _RUNTIME_TABLES[1:]
            }
            if source_counts != compact_counts:
                raise RuntimeError("runtime row counts changed during compaction")
            conn.commit()
        finally:
            conn.execute("DETACH DATABASE source_db")

        conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('storage_profile', ?)",
            (STORAGE_PROFILE,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('runtime_index_layout', 'resolver-only-v1')"
        )
        conn.execute("ANALYZE")
        conn.commit()
        conn.execute("VACUUM")

    _verify(destination)


def compact_evidence_database(source: Path, destination: Path) -> None:
    """Materialize dictionary-backed, lossless evidence storage.

    Repeated provenance labels and JSON metadata dominate the build evidence DB.
    The distribution stores each distinct value once and exposes a compatibility
    ``records`` view with the exact historical columns.  Consumers can therefore
    keep issuing normal SELECTs while the immutable artifact avoids the build-time
    composite UNIQUE index and repeated strings.
    """

    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        raise ValueError("evidence distribution destination must differ from source")
    destination.unlink(missing_ok=True)

    with closing(sqlite3.connect(destination, timeout=60.0)) as conn:
        _configure_build(conn)
        conn.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE source_snapshots (
                id INTEGER PRIMARY KEY,
                source_key TEXT NOT NULL,
                source_kind TEXT NOT NULL DEFAULT 'dataset',
                source_url TEXT NOT NULL DEFAULT '',
                final_url TEXT NOT NULL DEFAULT '',
                upstream_version TEXT NOT NULL DEFAULT '',
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
                retrieved_at TEXT NOT NULL,
                etag TEXT NOT NULL DEFAULT '',
                last_modified TEXT NOT NULL DEFAULT '',
                license_note TEXT NOT NULL DEFAULT '',
                record_count INTEGER NOT NULL DEFAULT 0 CHECK(record_count >= 0),
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX source_snapshots_source_idx
                ON source_snapshots(source_key, retrieved_at);

            CREATE TABLE lineage_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE source_title_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE source_episode_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE source_status_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE normalization_status_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE normalization_reason_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE normalized_episode_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE metadata_values(id INTEGER PRIMARY KEY, value TEXT NOT NULL);

            CREATE TABLE record_core (
                id INTEGER PRIMARY KEY,
                snapshot_id INTEGER NOT NULL REFERENCES source_snapshots(id) ON DELETE CASCADE,
                record_key TEXT NOT NULL,
                lineage_id INTEGER NOT NULL REFERENCES lineage_values(id),
                source_title_id INTEGER NOT NULL REFERENCES source_title_values(id),
                source_episode_id INTEGER NOT NULL REFERENCES source_episode_values(id),
                source_status_id INTEGER NOT NULL REFERENCES source_status_values(id),
                quality_score REAL,
                votes_up INTEGER NOT NULL DEFAULT 0,
                votes_down INTEGER NOT NULL DEFAULT 0,
                payload_sha256 BLOB NOT NULL DEFAULT X''
                    CHECK(length(payload_sha256) IN (0, 32)),
                normalization_status_id INTEGER NOT NULL REFERENCES normalization_status_values(id),
                normalization_reason_id INTEGER NOT NULL REFERENCES normalization_reason_values(id),
                normalized_anchor_id INTEGER CHECK(
                    normalized_anchor_id IS NULL OR normalized_anchor_id > 0
                ),
                normalized_episode_id INTEGER NOT NULL REFERENCES normalized_episode_values(id),
                metadata_id INTEGER NOT NULL REFERENCES metadata_values(id)
            );

            CREATE INDEX record_core_snapshot_idx ON record_core(snapshot_id);

            CREATE TABLE record_segments (
                record_id INTEGER NOT NULL REFERENCES record_core(id) ON DELETE CASCADE,
                source_segment_id TEXT NOT NULL,
                segment_type TEXT NOT NULL,
                start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
                end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
                media_duration_ms INTEGER CHECK(
                    media_duration_ms IS NULL OR media_duration_ms > 0
                ),
                PRIMARY KEY(record_id, source_segment_id)
            ) WITHOUT ROWID;

            CREATE VIEW records AS
            SELECT
                record.id,
                record.snapshot_id,
                record.record_key,
                lineage.value AS lineage_key,
                source_title.value AS source_title_key,
                source_episode.value AS source_episode_key,
                source_status.value AS source_status,
                record.quality_score,
                record.votes_up,
                record.votes_down,
                record.payload_sha256,
                normalization_status.value AS normalization_status,
                normalization_reason.value AS normalization_reason,
                record.normalized_anchor_id,
                normalized_episode.value AS normalized_episode_key,
                metadata_value.value AS metadata_json
            FROM record_core AS record
            JOIN lineage_values AS lineage ON lineage.id=record.lineage_id
            JOIN source_title_values AS source_title ON source_title.id=record.source_title_id
            JOIN source_episode_values AS source_episode ON source_episode.id=record.source_episode_id
            JOIN source_status_values AS source_status ON source_status.id=record.source_status_id
            JOIN normalization_status_values AS normalization_status
              ON normalization_status.id=record.normalization_status_id
            JOIN normalization_reason_values AS normalization_reason
              ON normalization_reason.id=record.normalization_reason_id
            JOIN normalized_episode_values AS normalized_episode
              ON normalized_episode.id=record.normalized_episode_id
            JOIN metadata_values AS metadata_value ON metadata_value.id=record.metadata_id;
            """
        )
        conn.execute("ATTACH DATABASE ? AS source_db", (source.resolve().as_posix(),))
        temporary_indexes: list[str] = []
        try:
            for table in ("metadata", "source_snapshots"):
                packed = _columns(conn, table)
                conn.execute(
                    f"INSERT INTO {table}({packed}) SELECT {packed} FROM source_db.{table}"
                )

            for table, column in _EVIDENCE_DICTIONARIES:
                conn.execute(
                    f"INSERT INTO {table}(value) "
                    f"SELECT DISTINCT {column} FROM source_db.records ORDER BY {column}"
                )
                index = f"temp_{table}_value_idx"
                conn.execute(f"CREATE UNIQUE INDEX {index} ON {table}(value)")
                temporary_indexes.append(index)

            conn.execute(
                """
                INSERT INTO record_core(
                    id, snapshot_id, record_key, lineage_id, source_title_id,
                    source_episode_id, source_status_id, quality_score, votes_up,
                    votes_down, payload_sha256, normalization_status_id,
                    normalization_reason_id, normalized_anchor_id,
                    normalized_episode_id, metadata_id
                )
                SELECT
                    record.id,
                    record.snapshot_id,
                    record.record_key,
                    lineage.id,
                    source_title.id,
                    source_episode.id,
                    source_status.id,
                    record.quality_score,
                    record.votes_up,
                    record.votes_down,
                    record.payload_sha256,
                    normalization_status.id,
                    normalization_reason.id,
                    record.normalized_anchor_id,
                    normalized_episode.id,
                    metadata_value.id
                FROM source_db.records AS record
                JOIN lineage_values AS lineage ON lineage.value=record.lineage_key
                JOIN source_title_values AS source_title
                  ON source_title.value=record.source_title_key
                JOIN source_episode_values AS source_episode
                  ON source_episode.value=record.source_episode_key
                JOIN source_status_values AS source_status
                  ON source_status.value=record.source_status
                JOIN normalization_status_values AS normalization_status
                  ON normalization_status.value=record.normalization_status
                JOIN normalization_reason_values AS normalization_reason
                  ON normalization_reason.value=record.normalization_reason
                JOIN normalized_episode_values AS normalized_episode
                  ON normalized_episode.value=record.normalized_episode_key
                JOIN metadata_values AS metadata_value
                  ON metadata_value.value=record.metadata_json
                """
            )
            conn.execute(
                """
                INSERT INTO record_segments(
                    record_id, source_segment_id, segment_type,
                    start_ms, end_ms, media_duration_ms
                )
                SELECT
                    record_id, source_segment_id, segment_type,
                    start_ms, end_ms, media_duration_ms
                FROM source_db.record_segments
                """
            )
            source_records = int(
                conn.execute("SELECT COUNT(*) FROM source_db.records").fetchone()[0]
            )
            source_segments = int(
                conn.execute(
                    "SELECT COUNT(*) FROM source_db.record_segments"
                ).fetchone()[0]
            )
            compact_records = int(
                conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
            )
            compact_segments = int(
                conn.execute("SELECT COUNT(*) FROM record_segments").fetchone()[0]
            )
            if (source_records, source_segments) != (compact_records, compact_segments):
                raise RuntimeError("evidence row counts changed during compaction")
            conn.commit()
        finally:
            conn.execute("DETACH DATABASE source_db")

        for index in temporary_indexes:
            conn.execute(f"DROP INDEX {index}")
        conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('storage_profile', ?)",
            (STORAGE_PROFILE,),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES('records_storage', 'dictionary-core-view')"
        )
        conn.execute("ANALYZE")
        conn.commit()
        conn.execute("VACUUM")

    _verify(destination)
