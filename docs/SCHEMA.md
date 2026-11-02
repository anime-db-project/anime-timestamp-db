# Schema v2

Schema v2 is the first data-bearing design. It separates normalized anime timestamps, source-addressable timestamps, and build evidence instead of forcing every upstream dataset into one identity model.

`schema_version` changes only when the SQLite table/column contract changes. Builder behavior can evolve independently through `build_format_version`.

## Runtime: `timestamps.db`

### `metadata`

Stores schema version, database role, generation timestamp, build format, consensus configuration, and the exact Anime Mapping DB snapshot/schema used for title enrichment.

### `sources` and `lineages`

A `source` answers where a timestamp row was imported from. A `lineage` answers who produced the independent timing evidence. Keeping them separate prevents a mirror or aggregator from creating a fake extra consensus vote.

Build-time mapping inputs are recorded in the evidence database and manifest even when they do not contribute timestamp rows to `sources`.

### `titles` / `title_ids`

One local anime title plus explicit provider IDs.

Title identity currently comes from three paths:

1. native MAL IDs in AniSkip;
2. MAL/AniList/AniDB/IMDb movie IDs supplied by safe AniBridge episode mappings;
3. direct accepted, conflict-free aliases from the published Anime Mapping DB.

Anime Mapping DB enrichment is intentionally **title-only**. If it adds a Kitsu, Shikimori, IMDb, TVDB, TMDB, aniSearch, or another provider ID, that does not prove that the provider's episode number `N` equals MAL episode `N`.

IMDb TV season descriptors are deliberately not inserted as title IDs because one TV season may span multiple anime catalogue entries.

### `episodes`

Normalized local playback-unit identity. Regular episodes normally use `ep:<n>`. AniDB-only non-regular scopes can use keys such as `anidb:S:1`, avoiding silent flattening of specials into regular numbering.

Films mapped by a source-local key `movie` are merged into `ep:1` when the same normalized title already has a native `ep:1`. This prevents duplicate local playback identities while preserving source references.

### `episode_ids`

Provider-specific episode identity:

```text
provider + title_external_id + scope + episode_number_text -> episode_id
```

This is intentionally separate from `episodes.episode_number`. MAL, AniList and AniDB episode numbering may differ even when title identity is agreed. AniDB scope is retained.

A `title_ids` alias alone never creates an `episode_ids` row.

### `episode_refs`

Maps one timestamp source's title/episode key to a normalized episode. A source reference is never allowed to point to two normalized episodes.

Movie normalization may repoint an existing source reference from local `movie` to canonical `ep:1`; the original source key itself is preserved.

### `segments`

Approved normalized source observations. Stores source and lineage, stable source-record ID, normalized segment type, start/end milliseconds, optional full media duration, quality score and vote counts.

### `source_segments`

Valid ranges that are not safely cross-database-normalized. Baha Anime Skip currently uses this table because its bulk database is keyed by Bahamut `videoSn` and does not provide a reusable anime-ID/episode mapping.

### `consensus_segments` / `consensus_members`

Consensus is materialized derived data, never a replacement for originals. Each row stores boundaries, media duration when available, member/source/lineage counts, confidence, algorithm, and tolerance. `consensus_members` keeps exact provenance back to every contributing normalized observation.

Consensus is built only after movie identity normalization and provider episode-index reconstruction.

## Evidence: `timestamps-evidence.db`

### `source_snapshots`

One downloaded input snapshot: original/final URL, SHA-256, byte size, retrieval time, ETag/Last-Modified, upstream version, license note, record count and additional metadata.

This includes timestamp sources and build-time identity sources such as AniBridge and Anime Mapping DB.

### `records`

One upstream logical record or one explicit build-time mapping decision.

Timestamp records store source status, scores/votes, payload hash, source title/episode references, normalization status/reason and normalized target when available.

Anime Mapping DB enrichment records store the MAL anchor, accepted direct aliases, aliases actually added, mapping conflicts, and local identity conflicts. They have no `record_segments` rows because they are identity evidence rather than timestamp observations.

SkipDB contributor identifiers are intentionally not copied.

### `record_segments`

The normalized timestamp range observed in a timestamp evidence record.

## Normalization statuses

Timestamp records commonly use:

- `mapped`: safe anime episode mapping found;
- `unmapped`: no safe one-to-one AniBridge mapping;
- `ambiguous`: identity conflict; runtime row suppressed;
- `source-only`: valid timestamp retained under its upstream episode key;
- `invalid`: malformed/missing identity or invalid range.

Build-time mapping evidence can also use `mapped` or `ambiguous` depending on whether aliases were attached safely.

## Segment types

Current normalized names include `opening`, `ending`, `recap`, and `preview`. Types remain text rather than a closed SQL enum so a useful future provider type does not require a schema migration merely to be stored.

## AniBridge projection

Only one-source-episode to one-target-episode projections are accepted. Ratio mappings (`|2`, `|-2`, etc.) represent split/combined episode granularity and are deliberately skipped. Non-contiguous target ranges without ratios can be projected by offset because one source unit still maps to one target unit.

Provider episode numbering is rebuilt as a deterministic derived index after import using the exact same pinned AniBridge payload used during normalization.

## Anime Mapping DB projection

Only a single direct accepted edge from an existing MAL node is considered. The upstream directional `conflicts` table is honored, and the timestamp builder performs a second local conflict check before adding an alias.

The builder does not:

- perform transitive graph traversal;
- merge two existing timestamp titles because an alias collides;
- infer episode numbers from a title edge;
- call Anime Mapping DB APIs or source-specific crawlers.

## Media cuts

When an upstream observation includes full media duration, that duration is stored with the segment. Consensus avoids clustering observations whose media duration differs substantially. Runtime lookups can pass playback duration to rank the closest cut first.

## Versioning

`PRAGMA user_version` and `metadata.schema_version` must both match `SCHEMA_VERSION`. Table/column contract changes require a schema version bump.

Build process changes that do not alter the SQLite contract use `build_format_version`. The movie-normalization/title-enrichment integration is a build-format change, not a schema-v3 migration.
