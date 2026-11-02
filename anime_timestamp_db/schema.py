from __future__ import annotations

SCHEMA_VERSION = 5
DEFAULT_RUNTIME_DB_NAME = "timestamps.db"
DEFAULT_EVIDENCE_DB_NAME = "timestamps-evidence.db"

RUNTIME_SCHEMA = r"""
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

-- Stable title identity comes from anime-mapping-db. We intentionally do not
-- copy provider aliases into this database: anchor_id is the cross-project key.
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

-- Provider-specific episode numbering is still useful because MAL/AniList/AniDB
-- can number the same playback unit differently. The provider title ID is not
-- duplicated here: anchor_id already identifies the normalized title.
CREATE TABLE episode_ids (
    anchor_id INTEGER NOT NULL REFERENCES titles(anchor_id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT '',
    episode_number_text TEXT NOT NULL,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    PRIMARY KEY(anchor_id, provider, scope, episode_number_text)
) WITHOUT ROWID;

CREATE INDEX episode_ids_episode_idx
    ON episode_ids(episode_id, provider, anchor_id);

CREATE TABLE episode_refs (
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_title_key TEXT NOT NULL DEFAULT '',
    source_episode_key TEXT NOT NULL,
    episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    source_episode_number_text TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(source_id, source_title_key, source_episode_key)
) WITHOUT ROWID;

CREATE INDEX episode_refs_episode_idx
    ON episode_refs(episode_id, source_id);

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
    votes_down INTEGER NOT NULL DEFAULT 0 CHECK(votes_down >= 0),
    UNIQUE(source_id, source_segment_id)
);

CREATE INDEX segments_episode_idx
    ON segments(episode_id, segment_type, start_ms, end_ms);
CREATE INDEX segments_source_idx
    ON segments(source_id, episode_id, segment_type);
CREATE INDEX segments_lineage_idx
    ON segments(lineage_id, episode_id, segment_type);
CREATE INDEX segments_duration_idx
    ON segments(episode_id, segment_type, media_duration_ms);

-- Timestamp datasets such as Baha Anime Skip can have accurate ranges but no
-- reusable cross-database episode identity. Keep those ranges queryable by the
-- upstream episode key without pretending that they are normalized anime IDs.
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
    media_duration_ms INTEGER CHECK(media_duration_ms IS NULL OR media_duration_ms > 0),
    UNIQUE(source_id, source_segment_id)
);

CREATE INDEX source_segments_lookup_idx
    ON source_segments(source_id, source_title_key, source_episode_key, segment_type);

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
    tolerance_ms INTEGER NOT NULL CHECK(tolerance_ms >= 0),
    UNIQUE(episode_id, segment_type, cluster_index)
);

CREATE INDEX consensus_episode_idx
    ON consensus_segments(episode_id, segment_type, cluster_index);
CREATE INDEX consensus_duration_idx
    ON consensus_segments(episode_id, segment_type, media_duration_ms);

CREATE TABLE consensus_members (
    consensus_id INTEGER NOT NULL REFERENCES consensus_segments(id) ON DELETE CASCADE,
    segment_id INTEGER NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    PRIMARY KEY(consensus_id, segment_id)
) WITHOUT ROWID;

CREATE INDEX consensus_members_segment_idx
    ON consensus_members(segment_id, consensus_id);
"""

EVIDENCE_SCHEMA = r"""
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

CREATE TABLE records (
    id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES source_snapshots(id) ON DELETE CASCADE,
    record_key TEXT NOT NULL,
    lineage_key TEXT NOT NULL,
    source_title_key TEXT NOT NULL DEFAULT '',
    source_episode_key TEXT NOT NULL DEFAULT '',
    source_status TEXT NOT NULL DEFAULT '',
    quality_score REAL,
    votes_up INTEGER NOT NULL DEFAULT 0,
    votes_down INTEGER NOT NULL DEFAULT 0,
    payload_sha256 TEXT NOT NULL DEFAULT '',
    normalization_status TEXT NOT NULL DEFAULT 'unprocessed',
    normalization_reason TEXT NOT NULL DEFAULT '',
    normalized_anchor_id INTEGER CHECK(
        normalized_anchor_id IS NULL OR normalized_anchor_id > 0
    ),
    normalized_episode_key TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(snapshot_id, record_key, lineage_key)
);

CREATE INDEX records_snapshot_idx ON records(snapshot_id, id);
CREATE INDEX records_normalization_idx
    ON records(normalization_status, snapshot_id);

CREATE TABLE record_segments (
    record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    source_segment_id TEXT NOT NULL,
    segment_type TEXT NOT NULL,
    start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
    media_duration_ms INTEGER CHECK(media_duration_ms IS NULL OR media_duration_ms > 0),
    PRIMARY KEY(record_id, source_segment_id)
) WITHOUT ROWID;
"""
