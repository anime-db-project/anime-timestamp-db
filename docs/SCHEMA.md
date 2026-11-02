# Schema v2

Schema v2 is the first data-bearing design. It separates normalized anime timestamps, source-addressable timestamps, and build evidence instead of forcing every upstream dataset into one identity model.

## Runtime: `timestamps.db`

### `metadata`

Stores schema version, database role, generation timestamp, build format, and consensus configuration.

### `sources` and `lineages`

A `source` answers where a row was imported from. A `lineage` answers who produced the independent timing evidence. Keeping them separate prevents a mirror or aggregator from creating a fake extra consensus vote.

### `titles` / `title_ids`

One local anime title plus explicit provider IDs. The current normalized SkipDB path can attach MAL, AniList and AniDB title IDs supplied by safe AniBridge episode mappings. IMDb movie IDs are also title-safe. IMDb TV season descriptors are deliberately not inserted as title IDs because one TV season may span multiple anime catalogue entries.

### `episodes`

Normalized local episode identity. Regular episodes normally use `ep:<n>`. AniDB-only non-regular scopes can use keys such as `anidb:S:1`, avoiding silent flattening of specials into regular numbering.

### `episode_ids`

Provider-specific episode identity:

```text
provider + title_external_id + scope + episode_number_text -> episode_id
```

This is intentionally separate from `episodes.episode_number`. MAL, AniList and AniDB episode numbering may differ even when title identity is agreed. AniDB scope is retained.

### `episode_refs`

Maps one timestamp source's title/episode key to a normalized episode. A source reference is never allowed to point to two normalized episodes.

### `segments`

Approved normalized source observations. Stores source and lineage, stable source-record ID, normalized segment type, start/end milliseconds, optional full media duration, quality score and vote counts.

### `source_segments`

Valid ranges that are not safely cross-database-normalized. Baha Anime Skip currently uses this table because its bulk database is keyed by Bahamut `videoSn` and does not provide a reusable anime-ID/episode mapping.

### `consensus_segments` / `consensus_members`

Consensus is materialized derived data, never a replacement for originals. Each row stores boundaries, media duration when available, member/source/lineage counts, confidence, algorithm, and tolerance. `consensus_members` keeps exact provenance back to every contributing normalized observation.

## Evidence: `timestamps-evidence.db`

### `source_snapshots`

One downloaded input snapshot: original/final URL, SHA-256, byte size, retrieval time, ETag/Last-Modified, upstream version, license note, record count and additional metadata.

### `records`

One upstream logical record. Stores source status, scores/votes, payload hash, source title/episode references, normalization status/reason and normalized target when available. SkipDB contributor identifiers are intentionally not copied.

### `record_segments`

The normalized timestamp range observed in an evidence record.

## Normalization statuses

- `mapped`: safe anime episode mapping found;
- `unmapped`: no safe one-to-one AniBridge mapping;
- `ambiguous`: identity conflict; runtime row suppressed;
- `source-only`: valid timestamp retained under its upstream episode key;
- `invalid`: malformed/missing identity or invalid range.

## Segment types

Current normalized names include `opening`, `ending`, `recap`, and `preview`. Types remain text rather than a closed SQL enum so a useful future provider type does not require a schema migration merely to be stored.

## AniBridge projection

Only one-source-episode to one-target-episode projections are accepted. Ratio mappings (`|2`, `|-2`, etc.) represent split/combined episode granularity and are deliberately skipped. Non-contiguous target ranges without ratios can be projected by offset because one source unit still maps to one target unit.

Provider episode numbering is rebuilt as a deterministic derived index after import using the exact same pinned AniBridge payload used during normalization.

## Media cuts

When an upstream observation includes full media duration, that duration is stored with the segment. Consensus avoids clustering observations whose media duration differs substantially. Runtime lookups can pass playback duration to rank the closest cut first.

## Versioning

`PRAGMA user_version` and `metadata.schema_version` must both match `SCHEMA_VERSION`. Table/column contract changes require a schema version bump. Build process changes that do not alter the SQLite contract use `build_format_version`.
