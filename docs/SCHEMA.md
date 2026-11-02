# Schema v4

Schema v4 extends the data-bearing design with explicit consensus eligibility so aggregator rows can remain queryable without manufacturing extra independent votes. Schema v3 introduced episode-mapping provenance/confidence; v4 adds aggregator-safe consensus semantics. It separates normalized anime timestamps, source-addressable timestamps, and build evidence instead of forcing every upstream dataset into one identity model.

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
2. anime IDs supplied by safe SkipDB episode projection through Anime Mapping DB plus AniBridge, and direct AniBridge movie mappings;
3. AniDB-native Open Anime Timestamps episodes projected through AniBridge;
4. direct accepted, conflict-free aliases from the published Anime Mapping DB.

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

Approved normalized source observations. Stores source and lineage, stable source-record ID, normalized segment type, start/end milliseconds, optional full media duration, quality score and vote counts. `mapping_method` and `mapping_confidence` (`0..1`) keep native/exact/inferred episode identity queryable. Schema v4 adds `consensus_eligible` (`0/1`): a valid range can stay queryable while being deliberately excluded from consensus when independent field-level provenance cannot be established.

### `source_segments`

Valid ranges that are not safely cross-database-normalized. Baha Anime Skip uses this table because its bulk database is keyed by Bahamut `videoSn`. SkipDB uses it for approved rows whose IMDb title is confidently anime but whose concrete season/episode mapping remains unresolved. Open Anime Timestamps uses it for AniDB episodes that cannot be projected safely through AniBridge.

### `consensus_segments` / `consensus_members`

Consensus is materialized derived data, never a replacement for originals. Each row stores boundaries, media duration when available, member/source/lineage counts, confidence, algorithm, and tolerance. `consensus_members` keeps exact provenance back to every contributing normalized observation.

Consensus is built only after movie identity normalization and provider episode-index reconstruction. Only `consensus_eligible=1` rows are considered. Within each timing cluster, weighted boundaries use at most one representative observation per `lineage_id`; mirrored copies of the same upstream lineage therefore cannot multiply voting weight. `consensus_members` still preserves all eligible member rows for auditability.

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

- `mapped`: exact anime episode mapping found;
- `mapped-inferred`: conservative same-season episode-offset inference found;
- `unmapped`: no supported anime identity/episode projection;
- `ambiguous`: identity conflict; runtime row suppressed;
- `source-only`: valid anime timestamp retained under its upstream episode key because the exact episode identity remains unresolved;
- `invalid`: malformed/missing identity or invalid range;
- `empty`: upstream record has no ranged timestamp fields (for example an OAT preview-only point marker retained in metadata).

Build-time mapping evidence can also use `mapped` or `ambiguous` depending on whether aliases were attached safely.

## Segment types

Current normalized names include `opening`, `ending`, `recap`, and `preview`. Types remain text rather than a closed SQL enum so a useful future provider type does not require a schema migration merely to be stored.

## SkipDB / AniBridge projection

SkipDB series do not rely on nonexistent `imdb_show` entries in AniBridge. The builder uses a two-stage identity bridge:

```text
SkipDB IMDb show
  -> Anime Mapping DB accepted TVDB/TMDB title identity
  -> AniBridge tvdb_show/tmdb_show season mapping
  -> MAL/AniList/AniDB episode
```

Conflicted TVDB/TMDB routes are suppressed. When both routes exist they must collapse to one coherent provider/episode identity; disagreement stays unresolved. A single unambiguous route is allowed but gets slightly lower mapping confidence.

Only one-source-episode to one-target-episode AniBridge projections are accepted. Ratio mappings (`|2`, `|-2`, etc.) represent split/combined episode granularity and are deliberately skipped. Non-contiguous target ranges without ratios can be projected by offset because one source unit still maps to one target unit.

After exact projection, a missing episode can be inferred only within the same IMDb season when at least two exact MAL anchors agree on both one MAL title and one constant target-minus-source episode offset. These rows are stored as `inferred-season-offset` with confidence `0.85`; exact dual-route and single-route mappings use `1.0` and `0.98` respectively.

Provider episode numbering is rebuilt as a deterministic derived index after title enrichment using the exact same pinned Anime Mapping DB and AniBridge snapshots used during normalization.

## Open Anime Timestamps / AniBridge projection

Open Anime Timestamps is keyed by AniDB title ID. Regular positive integer episode numbers use the direct episode bridge:

```text
Open Anime Timestamps AniDB title + episode
  -> AniBridge anidb:<id>:R
  -> MAL/AniList/AniDB episode
```

Fractional/zero/unresolved episode identities are retained source-only rather than flattened into regular numbering. AniDB `R` episode identity is recorded in `episode_ids` when projection succeeds.

The upstream `sources` array is record-level provenance. For a single reported source, the importer assigns the matching lineage (`open-anime-timestamps`, `open-anime-timestamps-chapter-data`, `aniskip`, `anime-skip`, or `better-vrv`). If several origins are listed, the record uses `open-anime-timestamps-aggregate` and its ranges are stored with `consensus_eligible=0`; the upstream format does not prove which individual field came from which origin.

`preview_start` is a point marker rather than a range. Because the runtime segment schema requires a proven end boundary, point-only preview starts are preserved in evidence metadata and are not converted into guessed skip ranges.

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

Build process changes that do not alter the SQLite contract use `build_format_version`. Schema v3 added segment-level `mapping_method` and `mapping_confidence`; schema v4 adds `segments.consensus_eligible` for aggregator-safe voting. The Open Anime Timestamps integration and lineage-aware consensus behavior use build format v6.
