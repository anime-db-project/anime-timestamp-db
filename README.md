> **AI-assisted project:** This project was developed with the help of AI.

# Anime Timestamp DB

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](DATA_LICENSE.md)

**Anime Timestamp DB** builds an auditable SQLite database of anime episode skip segments: openings, endings, recaps, previews, and other ranges.

It is the timestamp counterpart to [`anime-db-project/anime-mapping-db`](https://github.com/anime-db-project/anime-mapping-db). Source quirks stay in the builder; consumers get one stable local SQLite interface with original observations, provenance, provider IDs, and derived consensus.

## Real data inputs

The default build uses reproducible public bulk/static files. It does not call runtime anime timestamp APIs and does not crawl streaming sites.

| Input | Role | Runtime behavior |
| --- | --- | --- |
| [AniSkip public dataset](https://github.com/aniskip/sanitize-db-dump) | Primary MAL-native timestamp dataset | MAL title ID + episode number are imported directly. Current and legacy sanitized CSV schemas are supported. |
| [SkipDB](https://github.com/SkipDB-TV/skipdb) | Large supplementary timestamp dataset | IMDb titles are identified through Anime Mapping DB, then TVDB/TMDB season identities are projected through AniBridge to concrete anime episodes. Exact mappings enter runtime; conservative same-season offset inference is explicitly confidence-weighted; unresolved anime rows remain source-addressable. |
| [AniBridge mappings](https://github.com/anibridge/anibridge-mappings) | Episode identity bridge | Maps TVDB/TMDB show seasons and movies to MAL/AniList/AniDB playback units. SkipDB IMDb IDs first pass through Anime Mapping DB to reach these bridge identities. Split/combined ratio mappings are deliberately not projected. |
| [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) | Title-ID enrichment | The latest published `mappings.db.zst` is used only for direct, accepted, conflict-free title aliases. It does **not** invent provider episode numbering. |
| [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) | Source-addressable timestamp dataset | Stored by Bahamut `videoSn`. No fake MAL/AniList identity is invented. |

`open-anime-timestamps` is intentionally excluded from distributable builds while its upstream repository has no explicit license or equivalent public-dataset statement.

## What the build produces

`timestamps.db` contains two honest levels of timestamp coverage:

- `segments`: timestamps normalized to a concrete anime title and episode;
- `source_segments`: valid timestamps whose upstream episode key is known but which cannot be cross-database-normalized safely.

The builder also creates `timestamps-evidence.db`, which stores source snapshots, hashes, normalization decisions, votes/scores, and the exact evidence used to produce the runtime database.

Important runtime tables:

- `titles`, `title_ids`: normalized title identity and explicit provider aliases;
- `episodes`: local episode identity;
- `episode_ids`: provider-specific episode numbering and AniDB scopes;
- `episode_refs`: timestamp-source episode references;
- `segments`: original normalized timestamp observations;
- `source_segments`: source-addressable ranges such as Baha `videoSn`;
- `consensus_segments`, `consensus_members`: derived best ranges with exact membership traceability;
- `sources`, `lineages`: source provenance and independent evidence lineage.

All times are stored as integer milliseconds. See [`docs/SCHEMA.md`](docs/SCHEMA.md).

## Identity rules

The builder deliberately prefers missing data over a plausible but wrong identity.

- AniSkip MAL IDs are treated as native MAL identities.
- SkipDB series use the auditable chain `IMDb -> Anime Mapping DB -> TVDB/TMDB -> AniBridge -> anime episode`; no title-name matching is used.
- When both TVDB and TMDB routes independently resolve an episode to the same anime identity, the row is marked `exact-dual-bridge` with confidence `1.0`; a single unambiguous route is `exact-single-bridge` with confidence `0.98`.
- A missing episode may be filled only when at least two exact anchors in the same IMDb season agree on one MAL title and one constant episode offset. Such rows are marked `inferred-season-offset` with confidence `0.85`.
- AniBridge ratio mappings (`|2`, `|-2`, etc.) are skipped because they represent split/combined episode granularity.
- MAL, AniList and AniDB episode numbers are stored separately in `episode_ids`; one provider's numbering is never assumed to equal another's.
- AniDB scope is preserved for non-regular episodes.
- IMDb TV season descriptors are not promoted to global anime-title IDs because one TV season can span multiple independently catalogued anime entries.
- Anime Mapping DB contributes only **one-hop accepted title aliases with no directional conflict**.
- A title alias from Anime Mapping DB never creates a provider-specific episode number by itself.
- If a mapping alias is already attached to a different local title, it is suppressed and recorded as a conflict instead of merging the titles.
- Pending/rejected SkipDB rows never enter runtime `segments`. Approved anime rows whose episode identity still cannot be proven are retained in `source_segments` rather than discarded.
- Baha remains source-only until a bulk, auditable episode mapping exists.

### Movie normalization

A film can arrive from SkipDB as source episode key `movie` while AniSkip represents the same MAL title as episode `1`.

If both local identities exist under the same normalized title, the builder merges `movie` into canonical `ep:1` **before** rebuilding provider episode indexes and consensus. Source references remain intact, but duplicate local playback identities do not survive into the final database.

## Consensus

Source observations are never overwritten. `weighted-median-v1` materializes consensus separately and links every consensus row back to its exact members. Segment weight also includes `mapping_confidence`, so conservative SkipDB season-offset inference cannot vote as strongly as native or exact episode identity.

The algorithm groups by normalized episode and segment type, separates obviously different media cuts using total duration, clusters close/high-overlap ranges, uses quality/vote-aware weighted medians for boundaries, and stores member/source/lineage counts plus an agreement confidence score.

The default boundary tolerance is 5 seconds and is stored in metadata and the build manifest.

## Current real-data coverage

A validated schema-v3 build against the 2026-11-01 SkipDB dump contains:

- **3,484** normalized anime titles;
- **41,778** normalized episodes;
- **114,354** normalized source segments;
- **85,028** materialized consensus segments;
- **76,663** AniSkip runtime segments;
- **37,691** SkipDB runtime segments across **1,142** normalized titles and **19,289** episodes;
- **919** additional approved SkipDB anime segments retained source-only because episode identity remains unresolved;
- **19,681** Baha source-only segments.

For SkipDB specifically, the same dump contains 809 IMDb titles that Anime Mapping DB can directly tie to anime catalog identities. The bridge normalizes 37,283 exact series segments, 10 exact movie segments, and 408 conservatively inferred same-season segments; unresolved anime rows are preserved instead of dropped. Counts are snapshot-dependent and the authoritative numbers for any artifact live in its `manifest.json` and `audit.json`.

## Evidence and reproducibility

Every downloaded input is recorded with:

- original and final redirected URL;
- SHA-256 and byte size;
- retrieval time;
- ETag / Last-Modified when available;
- source role and license note;
- upstream build/version metadata where available.

Anime Mapping DB is consumed as a **build-time bulk artifact**, not through its resolver API. The compressed release database is hash-addressed in the local build cache, decompressed atomically, and checked with SQLite `quick_check` before use.

AniSkip user identifiers are never copied into compiled artifacts or record hashes. The current sanitized export no longer contains them; compatibility with the older sanitized schema still explicitly drops `user_id`.

## Actions artifacts, not Releases

For now database builds are uploaded only as GitHub Actions artifacts. No database Release is created.

`.github/workflows/build.yml` runs on pushes to `main`, manual dispatch, and a daily schedule. A successful build uploads for 14 days:

```text
timestamps.db
timestamps.db.zst
timestamps-evidence.db
timestamps-evidence.db.zst
manifest.json
audit.json
SHA256SUMS
DATA_LICENSE.md
THIRD_PARTY_NOTICES.md
ANISKIP_PUBLIC_DATA_NOTICE.md
SKIPDB_DATA_LICENSE.txt
BAHA_LICENSE.txt
ANIBRIDGE_LICENSE.txt
MAPPING_DB_DATA_LICENSE.md
MAPPING_DB_THIRD_PARTY_NOTICES.md
```

The Actions job summary prints normalized/source-only coverage, title/episode ID counts, source import results, movie-normalization stats, title-enrichment stats, episode-index stats, and consensus stats.

This gives us real build history and downloadable databases without turning every schema/build experiment into a permanent GitHub Release.

## Local build

Requires Python 3.11+.

```bash
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
```

Audit an existing build:

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## Lookup

Normalized source observations:

```bash
anime-timestamp-db lookup \
  --db artifacts/timestamps.db \
  --provider mal \
  --id 5114 \
  --episode 1
```

Consensus:

```bash
anime-timestamp-db lookup \
  --db artifacts/timestamps.db \
  --provider mal \
  --id 5114 \
  --episode 1 \
  --consensus
```

If playback duration is known, it can be used to rank the closest media cut:

```bash
anime-timestamp-db lookup \
  --db artifacts/timestamps.db \
  --provider mal \
  --id 5114 \
  --episode 1 \
  --duration-ms 1440000 \
  --consensus
```

AniDB specials can use an explicit scope:

```bash
anime-timestamp-db lookup \
  --db artifacts/timestamps.db \
  --provider anidb \
  --id 12345 \
  --episode 1 \
  --scope S
```

Baha source lookup:

```bash
anime-timestamp-db source-lookup \
  --db artifacts/timestamps.db \
  --source baha \
  --episode-key 123456
```

Python:

```python
from anime_timestamp_db import TimestampResolver

resolver = TimestampResolver("artifacts/timestamps.db")
segments = resolver.get_segments_by_episode("mal", "5114", 1)
ids = resolver.title_ids("mal", "5114")
key = resolver.episode_key("mal", "5114", 1)
consensus = resolver.get_consensus("mal", "5114", key) if key else []
baha = resolver.get_source_segments("baha", "123456")
```

`title_ids()` can expose Anime Mapping DB aliases even when that provider has no independently proven episode-number mapping. In that case use the already-normalized `episode_key` or resolve the episode through a provider that has an explicit `episode_ids` entry.

## Audit contract

Every Actions build must pass more than `PRAGMA integrity_check`:

- zero foreign-key errors;
- no invalid timestamp ranges;
- consensus member counts must match their membership table;
- no normalized episode may be left without a runtime segment;
- no title may retain both local `movie` and canonical `ep:1` episode identities;
- every provider-specific episode ID must belong to the same normalized title;
- both normalized and source-only real-data coverage must be non-empty;
- evidence records and evidence segments must be non-empty.

The exact counts are written to `audit.json` and `manifest.json`.

## File extension

The project uses `timestamps.db` for consistency with `anime-mapping-db` and `mappings.db`. SQLite does not assign meaning to `.db`, `.sqlite`, or `.sqlite3`.

## Licensing

Project code is Apache-2.0. Compiled data follows upstream database terms.

The build includes AniSkip public sanitized data, SkipDB, Baha Anime Skip, AniBridge-derived identity data, and direct accepted title aliases from Anime Mapping DB. Anime Mapping DB itself is a compiled mapping database with mixed upstream terms, including sources published under ODbL/DbCL and sources with their own attribution/licensing caveats.

Read [`DATA_LICENSE.md`](DATA_LICENSE.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and the bundled source-specific notices before redistributing a compiled database.
