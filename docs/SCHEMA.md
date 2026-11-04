# Schema v6

Schema v6 retains Anime Mapping DB's stable `amdb:<anchor_id>` as the cross-project identity and adds a compact `source_title_refs` table for **independently verified title-only links**. The timestamp database still never duplicates MAL, AniList, AniDB, Kitsu, TVDB, TMDB, IMDb, or other generic mapping aliases.

Schema v6 extends v5. A source may now contribute a proven AMDB title and unresolved source-native episode timings without fabricating a canonical episode. The v5-to-v6 SQLite table contract is a schema change; clients checking the exact schema version must update.

`schema_version` changes when the SQLite table/column contract changes. Builder-only behavior is versioned separately through `build_format_version`.

## Identity contract

There are now two layers with different responsibilities:

```text
anime-mapping-db
  amdb:<anchor_id>
      |
      v
anime-timestamp-db
  title / episode / timestamp data
```

`anchor_id` is the durable title identity shared between the two databases. Provider aliases stay in Anime Mapping DB and can be resolved there when needed.

The timestamp builder consumes a pinned `mappings.db.zst`, verifies/decompresses it, and resolves source-native IDs to `anchor_id` during the build. It does **not** copy Anime Mapping DB's provider alias graph into `timestamps.db` or `timestamps-evidence.db`.

## Runtime: `timestamps.db`

### `metadata`

Stores schema version, database role, generation/build versions, consensus configuration, identity namespace (`amdb`), and the exact Anime Mapping DB snapshot/schema used during the build.

### `sources` and `lineages`

A `source` answers where a timestamp observation was imported from. A `lineage` answers which independent timing source produced it. Keeping these separate prevents mirrors and aggregators from multiplying one upstream consensus vote.

Build-time mapping inputs are recorded in evidence/manifest metadata even when they do not contribute timestamp rows to `sources`.

### `titles`

```text
titles
  anchor_id INTEGER PRIMARY KEY
  display_title TEXT
```

A runtime title is directly keyed by Anime Mapping DB's stable numeric anchor. The public representation is `amdb:<anchor_id>`. Titles can exist without any canonical episodes when a source's title ID is proven but episode numbering remains unresolved.

There is deliberately no `title_ids` table in schema v6. External title aliases belong to Anime Mapping DB.

### `source_title_refs`

A small, audited link from a **source-native** title key to the proven AMDB anchor:

```text
source_id + source_title_key -> anchor_id + identity_method
```

`source_title_key` remains necessary to look up unresolved `source_segments`; `identity_method` records the independent proof (for example `exact-anilist-id`). This is not a second global provider-alias database. Each `(source_id, source_title_key)` has at most one AMDB anchor; changing it to a different anchor raises an identity conflict. A title may have no normalized `episodes` if all its source timings are still unresolved.

### `episodes`

```text
episodes
  id
  anchor_id -> titles.anchor_id
  episode_key
  episode_number_text
  episode_number
  is_special
  duration_ms

UNIQUE(anchor_id, episode_key)
```

`episode_key` is the timestamp database's normalized playback-unit key. Regular episodes normally use `ep:<n>`.

Films that arrive from SkipDB as source key `movie` are merged into canonical `ep:1` when the same `anchor_id` already has a native `ep:1`. Source references remain intact.

### `episode_ids`

Provider episode numbering is retained without duplicating provider title IDs:

```text
anchor_id + provider + scope + episode_number_text -> episode_id
```

This is intentionally separate from `episodes.episode_number`. MAL, AniList and AniDB episode numbering can differ even when all three provider titles resolve to the same AMDB anchor.

The provider's **title** ID is not stored here. At build time it is checked against Anime Mapping DB; after normalization the stable `anchor_id` is enough to identify the title.

Fractional numeric episode tokens such as `12.5` are preserved and are never truncated to an integer.

### `episode_refs`

Maps one timestamp source's own title/episode key to a normalized episode:

```text
source_id + source_title_key + source_episode_key -> episode_id
```

These source-native keys are retained because they are provenance, not cross-project identity. One source reference cannot point to two normalized episodes.

### `segments`

Approved observations normalized to an AMDB title and concrete episode. Each row stores:

- source and lineage;
- compact stable source segment ID;
- segment type;
- integer millisecond start/end;
- optional media duration;
- quality/votes;
- mapping method/confidence;
- `consensus_eligible`.

### `source_segments`

Valid ranges whose exact cross-database episode identity cannot be proven safely. Examples include Baha `videoSn` and unresolved but still useful source-native episodes.

The builder prefers retaining a valid observation here over inventing an AMDB episode identity. A source-native title with a verified `source_title_refs` entry can be queried by AMDB anchor via `TimestampResolver.get_source_segments_by_anchor()` and `source-anchor --anchor amdb:N`. The native source episode key is preserved; these ranges do not join the canonical `segments` or consensus until a separate episode proof exists.

### `consensus_segments` / `consensus_members`

Consensus is materialized derived data and never overwrites original observations. Every consensus row retains exact membership back to source `segments`.

Only `consensus_eligible=1` observations vote. Within a timing cluster, at most one representative per independent lineage contributes voting weight, preventing mirrors/aggregators from duplicating one source vote.

## Evidence: `timestamps-evidence.db`

### `source_snapshots`

One downloaded build input with source/final URL, SHA-256, byte size, retrieval time, ETag/Last-Modified, upstream version, license note, record count, and compact metadata.

Anime Mapping DB is represented by a single snapshot describing its role as the stable title identity resolver. Schema v5 no longer materializes thousands of alias-enrichment evidence rows.

### `records`

One upstream timestamp logical record.

Important normalization columns include:

```text
normalization_status
normalization_reason
normalized_anchor_id
normalized_episode_key
```

`normalized_anchor_id` replaces the v4 pair of normalized provider + normalized provider title ID.

Evidence metadata is intentionally compact. Large repeated Anime Mapping DB alias dictionaries and AniBridge target lists are not copied into every row when the same information remains reconstructible from the pinned source snapshot. Full per-record SHA-256 digests are stored as 32-byte BLOBs rather than 64-character hex text; synthetic AniSkip/SkipDB record IDs retain a source prefix plus a 128-bit digest token while the full digest remains available in evidence.

### `record_segments`

The exact timestamp range observed in an evidence record.

## Source normalization

### AniSkip

```text
AniSkip MAL title ID
  -> Anime Mapping DB
  -> amdb:<anchor_id>
  -> native episode number
```

AniSkip remains MAL-native at the source boundary, but MAL title IDs are not duplicated as runtime title aliases. If a MAL title has no stable AMDB anchor, its valid ranges remain source-addressable rather than being assigned a guessed title.

### SkipDB / AniBridge

```text
SkipDB IMDb title
  -> Anime Mapping DB TVDB/TMDB identity
  -> AniBridge season/episode mapping
  -> provider episode targets
  -> Anime Mapping DB anchor verification
  -> amdb:<anchor_id> + normalized episode
```

No title-name matching is used. Conflicted routes are suppressed. Ratio/split/combined mappings are not flattened.

A missing episode can be inferred only when conservative same-season anchor evidence agrees on one title and one constant offset; inferred rows retain lower mapping confidence.

### Open Anime Timestamps

```text
OAT AniDB title + regular episode
  -> AniBridge AniDB:R mapping
  -> provider episode targets
  -> Anime Mapping DB anchor verification
  -> amdb:<anchor_id> + normalized episode
```

Single-source provenance keeps its own lineage. Multi-source aggregate rows remain queryable but are `consensus_eligible=0` because field-level provenance is unavailable.

Point-only `preview_start` markers remain evidence metadata and are not turned into guessed ranges.

### Live AniSkip and Anime Skip API checkpoints

AniSkip API observations are MAL-native and reuse AniSkip's consensus lineage.
Anime Skip observations retain their original upstream lineages; mirrored
data does not create independent consensus votes.

For Anime Skip, native AniList title and episode numbers are never equated to
MAL numbers by arithmetic. The builder first checks independently proven
`episode_ids` for that AMDB anchor, which are indexed before API ingestion.
Otherwise, a uniquely reversible, one-to-one AniBridge regular AniDB
episode mapping must explicitly identify the same AniList episode and a MAL
episode, with all three provider title IDs accepted into one AMDB anchor.
Conflicting UUIDs, season-local numbers with no identity proof, split/combined
mappings, ambiguous ranges, and existing episode-index conflicts are rejected
for canonical import but preserved in `source_segments`.

Bridged observations use `mapping_method=exact-anibridge-api` with the
explicit AniDB and MAL episode proof recorded in the evidence metadata.
These matches may add previously absent `titles` or `episodes` while leaving
uncertain observations source-addressable rather than guessed.

### Baha Anime Skip

Baha remains source-addressable by upstream `videoSn`. No MAL/AniList/AMDB identity is invented unless a future auditable bulk mapping exists.

## Resolver behavior

The primary lookup key is `amdb:<anchor_id>` and requires only `timestamps.db`.

For convenience, `TimestampResolver` can also receive a matching Anime Mapping DB file:

```python
resolver = TimestampResolver(
    "timestamps.db",
    mapping_path="mappings.db",
)
```

Then MAL/AniList/AniDB/etc. title IDs can be resolved dynamically through Anime Mapping DB without storing their aliases inside the timestamp database.

This separation keeps the timestamp artifact smaller and gives every anime-db-project database one shared title identity source of truth.

## Audit contract

A valid runtime/evidence pair requires:

- matching schema v6 metadata and `PRAGMA user_version`;
- valid source-title reference foreign keys and no disagreement with independently mapped episode references;
- SQLite integrity success;
- zero foreign-key errors;
- no invalid timestamp ranges;
- every `episode_ids.anchor_id` to match its episode's `anchor_id`;
- no duplicate local `movie` + canonical `ep:1` identity for one title;
- consensus membership counts to match actual membership rows;
- no normalized episode without a runtime segment;
- non-empty normalized and source-only coverage;
- non-empty evidence records and ranges.

Exact counts are snapshot-dependent and live in `manifest.json` and `audit.json`.

## Versioning history

- v3: segment-level mapping method/confidence.
- v4: explicit consensus eligibility for aggregator-safe voting.
- v5: stable AMDB anchor title identity; removes copied `title_ids`, removes duplicated provider title IDs from `episode_ids`, and replaces normalized provider title columns in evidence with `normalized_anchor_id`.
- v6: adds `source_title_refs` for stable source-native title links, supporting title-only AMDB rows and AMDB-based lookup of unresolved source-native episode segments.
