from __future__ import annotations

SCHEMA_VERSION = 1
DEFAULT_RUNTIME_DB_NAME = "timestamps.db"
DEFAULT_EVIDENCE_DB_NAME = "timestamps-evidence.db"

RUNTIME_SCHEMA = """
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
    id INTEGER PRIMARY KEY,
    canonical_provider TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    UNIQUE(canonical_provider, canonical_id)
);

CREATE TABLE title_ids (
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title_id INTEGER NOT NULL REFERENCES titles(id) ON DELETE CASCADE,
    PRIMARY KEY(provider, external_id)
) WITHOUT ROWID;

CREATE INDEX title_ids_title_idx
    ON title_ids(title_id, provider, external_id);

CREATE TABLE episodes (
    id INTEGER PRIMARY KEY,
    title_id INTEGER NOT NULL REFERENCES titles(id) ON DELETE CASCADE,
    episode_key TEXT NOT NULL,
    episode_number_text TEXT NOT NULL DEFAULT '',
    episode_number REAL,
    season_number INTEGER,
    season_episode_number REAL,
    is_special INTEGER NOT NULL DEFAULT 0 CHECK(is_special IN (0, 1)),
    duration_ms INTEGER CHECK(duration_ms IS NULL OR duration_ms > 0),
    UNIQUE(title_id, episode_key)
);

CREATE INDEX episodes_title_idx
    ON episodes(title_id, episode_key);

CREATE TABLE episode_refs (
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_episode_key TEXT NOT NULL,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    source_title_key TEXT NOT NULL DEFAULT '',
    source_episode_number_text TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(source_id, source_episode_key)
) WITHOUT ROWID;

CREATE INDEX episode_refs_episode_idx
    ON episode_refs(episode_id, source_id);

CREATE TABLE segments (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    lineage_id INTEGER NOT NULL REFERENCES lineages(id),
    source_segment_id TEXT NOT NULL DEFAULT '',
    segment_type TEXT NOT NULL,
    start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
    confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    is_derived INTEGER NOT NULL DEFAULT 0 CHECK(is_derived IN (0, 1)),
    UNIQUE(
        episode_id,
        source_id,
        lineage_id,
        source_segment_id,
        segment_type,
        start_ms,
        end_ms
    )
);

CREATE INDEX segments_episode_idx
    ON segments(episode_id, segment_type, start_ms, end_ms);
CREATE INDEX segments_source_idx
    ON segments(source_id, episode_id, segment_type);
CREATE INDEX segments_lineage_idx
    ON segments(lineage_id, episode_id, segment_type);

CREATE TABLE consensus_segments (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    segment_type TEXT NOT NULL,
    cluster_index INTEGER NOT NULL,
    start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
    member_count INTEGER NOT NULL CHECK(member_count > 0),
    lineage_count INTEGER NOT NULL CHECK(lineage_count > 0),
    algorithm TEXT NOT NULL,
    tolerance_ms INTEGER NOT NULL CHECK(tolerance_ms >= 0),
    UNIQUE(episode_id, segment_type, cluster_index)
);

CREATE INDEX consensus_episode_idx
    ON consensus_segments(episode_id, segment_type, cluster_index);

CREATE TABLE consensus_members (
    consensus_id INTEGER NOT NULL REFERENCES consensus_segments(id) ON DELETE CASCADE,
    segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    PRIMARY KEY(consensus_id, segment_id)
) WITHOUT ROWID;

CREATE INDEX consensus_members_segment_idx
    ON consensus_members(segment_id, consensus_id);
"""

EVIDENCE_SCHEMA = """
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE source_snapshots (
    id INTEGER PRIMARY KEY,
    source_key TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    upstream_version TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    retrieved_at TEXT NOT NULL,
    license_note TEXT NOT NULL DEFAULT '',
    record_count INTEGER NOT NULL DEFAULT 0 CHECK(record_count >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX source_snapshots_source_idx
    ON source_snapshots(source_key, retrieved_at);

CREATE TABLE records (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES source_snapshots(id) ON DELETE CASCADE,
    record_key TEXT NOT NULL,
    lineage_key TEXT NOT NULL,
    source_title_key TEXT NOT NULL DEFAULT '',
    source_episode_key TEXT NOT NULL DEFAULT '',
    payload_sha256 TEXT NOT NULL DEFAULT '',
    UNIQUE(snapshot_id, record_key, lineage_key)
);

CREATE INDEX records_snapshot_idx
    ON records(snapshot_id, id);

CREATE TABLE record_segments (
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    source_segment_id TEXT NOT NULL DEFAULT '',
    segment_type TEXT NOT NULL,
    start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
    confidence REAL CHECK(confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    PRIMARY KEY(
        record_id,
        source_segment_id,
        segment_type,
        start_ms,
        end_ms
    )
) WITHOUT ROWID;
"""
