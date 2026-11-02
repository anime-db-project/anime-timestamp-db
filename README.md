> **AI-assisted project:** This project was developed with the help of AI.

# Anime Timestamp DB

**Anime Timestamp DB** is a standalone SQLite database project for collecting, normalizing, auditing, and distributing anime episode timestamp segments such as openings, endings, recaps, previews, credits, and other skippable ranges.

The project is designed as the timestamp counterpart to [`anime-db-project/anime-mapping-db`](https://github.com/anime-db-project/anime-mapping-db): consumers should eventually download a prebuilt `timestamps.db` release asset and query it locally instead of depending on many runtime APIs.

## Current status

The repository is in **schema-first bootstrap**. The database model, provenance rules, local resolver, tests, and CI are being stabilized before any network API adapters or crawlers are added.

No external timestamp dataset is imported by the current code yet.

## Design goals

- One compact local SQLite database for runtime consumers.
- Source-specific timestamps remain available; data is not flattened into one anonymous answer.
- Provenance distinguishes the **import source** from the **independent evidence lineage**.
- Duplicate aggregation does not create duplicate votes. For example, an AniSkip timestamp republished by another dataset remains AniSkip evidence.
- Title identifiers are queryable through provider/ID pairs and can later be normalized with `anime-mapping-db` during builds.
- Episodes keep a source-neutral local key plus source-specific episode references.
- Raw/import audit metadata is kept outside the runtime lookup path in a separate evidence database.
- Consensus timestamps are derived data and always retain links to their contributing source segments.
- Database files are release artifacts, not files committed directly to the repository.

## Planned release artifacts

Once import/build behavior is stable, releases are expected to contain at least:

```text
timestamps.db
timestamps.db.zst
timestamps-evidence.db
timestamps-evidence.db.zst
manifest.json
SHA256SUMS
```

The `.db` extension is intentional and matches `anime-mapping-db`. SQLite does not require a specific extension; `.db`, `.sqlite`, and `.sqlite3` can all contain the same SQLite file format.

## Runtime model

The runtime database is centered around these entities:

```text
sources ───────────────┐
                      │
lineages ──────────────┼── segments ── consensus_members ── consensus_segments
                      │       │
                      │       ▼
titles ── title_ids ──┴── episodes ── episode_refs
```

### Sources vs lineages

This distinction is important.

- `source` means **where the record was imported from**.
- `lineage` means **who originally produced the independent timing evidence**.

Example:

```text
source = open-anime-timestamps
lineage = aniskip
```

means that the row came from an `open-anime-timestamps` dump but the timing itself originated from AniSkip. A future consensus builder must count the lineage, not the number of mirrors/aggregators that republish it.

## Episode keys

`episodes.episode_key` is an opaque, normalized local key rather than a hard-coded integer-only episode number. Importers will later be responsible for generating stable keys such as regular episodes, specials, or season-scoped episodes without forcing every upstream database into one numbering convention.

Numeric columns are optional helpers for common cases and sorting; source-specific numbering is preserved separately in `episode_refs`.

## Segment types

`segment_type` is stored as normalized text instead of a closed SQL enum so new upstream segment classes do not require a schema migration. Initial normalized names are expected to include:

```text
opening
ending
mixed-opening
mixed-ending
recap
preview
credits
other
```

## Why a separate evidence database?

Runtime consumers need fast episode and segment lookup, not import history. Build/audit information therefore belongs in `timestamps-evidence.db`, while `timestamps.db` remains focused on lookup data.

The evidence database is intended to record source snapshots, hashes, upstream versions, record keys, lineage, and normalized observed segment ranges. This follows the same runtime/evidence separation used by `anime-mapping-db`.

## Deferred until the schema is stable

The following are intentionally **not implemented yet**:

- AniSkip API ingestion
- Anime Skip GraphQL ingestion
- IntroDB / PublicMetaDB / TheIntroDB ingestion
- any crawler or scraper
- automatic consensus generation
- GitHub release publishing

The first external inputs should be reproducible bulk/local datasets where possible, for example Baha Anime Skip, `open-anime-timestamps`, and SkipDB. API-only sources can be added after the storage and provenance model has survived real dump imports.

## Development

Requires Python 3.11+.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Create empty schema files:

```bash
anime-timestamp-db init --db timestamps.db --evidence-db timestamps-evidence.db
```

Inspect a runtime database:

```bash
anime-timestamp-db inspect --db timestamps.db
```

## Licensing

Project code is licensed under Apache-2.0. Dataset licensing is separate and will follow the terms of each upstream source; see `DATA_LICENSE.md` before distributing compiled data.
