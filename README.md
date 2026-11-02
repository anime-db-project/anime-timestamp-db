> **AI-assisted project:** This project was developed with the help of AI.

# Anime Timestamp DB

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](DATA_LICENSE.md)

**Anime Timestamp DB** builds an auditable SQLite database of anime episode skip segments: openings, endings, recaps, previews, and other ranges.

It is the timestamp counterpart to [`anime-db-project/anime-mapping-db`](https://github.com/anime-db-project/anime-mapping-db). Source quirks stay in the builder; consumers get one stable local SQLite interface.

## Real data inputs

The default build uses reproducible public bulk/static files. It does not call runtime anime timestamp APIs and does not crawl streaming sites.

| Input | Role | Runtime behavior |
| --- | --- | --- |
| [SkipDB](https://github.com/SkipDB-TV/skipdb) | Timestamp dataset | `approved` rows enter runtime only when AniBridge gives a safe one-to-one anime episode mapping. Other public statuses remain evidence-only. |
| [AniBridge mappings](https://github.com/anibridge/anibridge-mappings) | Episode identity bridge | Maps IMDb show season/episode numbering to MAL/AniList/AniDB. Split/combined ratio mappings are deliberately not projected. |
| [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) | Timestamp dataset | Stored by Bahamut `videoSn` as source-addressable ranges. No fake MAL/AniList identity is invented. |

`open-anime-timestamps` is intentionally excluded from distributable builds while its upstream repository has no explicit license.

## Runtime model

`timestamps.db` contains two honest levels of coverage:

- `segments`: timestamps normalized to an anime title and episode;
- `source_segments`: valid timestamps whose upstream episode key is known but which cannot be cross-database-normalized safely.

Important tables:

- `titles`, `title_ids`: normalized title identity;
- `episodes`: local episode identity;
- `episode_ids`: provider-specific episode numbering and AniDB scopes;
- `episode_refs`: timestamp-source episode references;
- `segments`: original approved normalized observations;
- `source_segments`: source-addressable ranges such as Baha `videoSn`;
- `consensus_segments`, `consensus_members`: derived best ranges with complete membership traceability;
- `sources`, `lineages`: import provenance and independent evidence lineage.

All times are stored as integer milliseconds. See [`docs/SCHEMA.md`](docs/SCHEMA.md).

## Evidence database

`timestamps-evidence.db` keeps build/audit material out of the runtime hot path. It records source snapshot URLs and hashes, retrieval metadata, upstream record status, normalization result/reason, source identifiers, scores/votes, and normalized timestamp ranges.

SkipDB `submitted_by` identifiers are deliberately not copied into the compiled evidence database. A whole-record SHA-256 is enough to distinguish upstream observations without republishing contributor identifiers.

## Mapping safety

The builder prefers missing data over a plausible but wrong mapping.

- AniBridge ratio mappings (`|2`, `|-2`, etc.) are skipped because they represent split/combined episode granularity.
- Conflicting title identities are suppressed instead of merged heuristically.
- MAL, AniList and AniDB episode numbers are stored separately in `episode_ids`; one provider's numbering is never assumed to equal another's.
- AniDB scope is preserved for non-regular episodes.
- IMDb TV season descriptors are not promoted to global anime-title IDs because one TV season can span multiple independently catalogued anime entries.
- Pending/rejected SkipDB rows never enter runtime `segments`.
- Baha remains source-only until a bulk, auditable episode mapping exists.

## Consensus

Source observations are never overwritten. `weighted-median-v1` materializes consensus separately and links every consensus row back to its exact members.

The algorithm groups by normalized episode and segment type, separates obviously different media cuts using total duration, clusters close/high-overlap ranges, uses quality/vote-aware weighted medians for boundaries, and stores member/source/lineage counts plus an agreement confidence score.

The default boundary tolerance is 5 seconds and is stored in metadata and the build manifest.

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
SKIPDB_DATA_LICENSE.txt
BAHA_LICENSE.txt
ANIBRIDGE_LICENSE.txt
```

This gives us real build history without turning every schema experiment into a permanent GitHub Release.

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
key = resolver.episode_key("mal", "5114", 1)
consensus = resolver.get_consensus("mal", "5114", key) if key else []
baha = resolver.get_source_segments("baha", "123456")
```

## Audit contract

Every Actions build must pass more than `PRAGMA integrity_check`:

- zero foreign-key errors;
- no invalid timestamp ranges;
- consensus member counts must match their membership table;
- no normalized episode may be left without a runtime segment;
- every provider-specific episode ID must belong to the same normalized title;
- both normalized and source-only real-data coverage must be non-empty;
- evidence records and evidence segments must be non-empty.

The exact counts are written to `audit.json` and `manifest.json`.

## File extension

The project uses `timestamps.db` for consistency with `anime-mapping-db` and `mappings.db`. SQLite does not assign meaning to `.db`, `.sqlite`, or `.sqlite3`.

## Licensing

Project code is Apache-2.0. Compiled data follows upstream database terms. SkipDB is the restrictive component of the default data build: read [`DATA_LICENSE.md`](DATA_LICENSE.md) and the bundled upstream `SKIPDB_DATA_LICENSE.txt` before redistributing a compiled database.
