> **AI-assisted project:** This project was developed with the help of AI.

# Anime Timestamp DB

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](DATA_LICENSE.md)

**Anime Timestamp DB** builds an auditable SQLite database of anime episode skip segments: openings, endings, recaps, previews, and other ranges.

It is the timestamp counterpart to [`anime-db-project/anime-mapping-db`](https://github.com/anime-db-project/anime-mapping-db). Schema v6 uses Anime Mapping DB's stable `amdb:<anchor_id>` as the shared title identity instead of duplicating MAL, AniList, AniDB, Kitsu, IMDb, TVDB, TMDB, and other title aliases inside the timestamp database.

## Real data inputs

The default build uses reproducible public bulk/static files. It does not call runtime anime timestamp APIs and does not crawl streaming sites.

| Input | Role | Runtime behavior |
| --- | --- | --- |
| [AniSkip public dataset](https://github.com/aniskip/sanitize-db-dump) | Primary MAL-native timestamp dataset | MAL title IDs are resolved through Anime Mapping DB to stable AMDB anchors; native episode numbering is retained. |
| [SkipDB](https://github.com/SkipDB-TV/skipdb) | Large supplementary timestamp dataset | IMDb titles pass through Anime Mapping DB and AniBridge to concrete anime episodes; unresolved valid anime rows remain source-addressable. |
| [AniBridge mappings](https://github.com/anibridge/anibridge-mappings) | Episode identity bridge | Projects TVDB/TMDB/AniDB episode numbering to MAL/AniList/AniDB playback units. Split/combined ratio mappings are deliberately not flattened. |
| [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) | Stable title identity | Supplies `amdb:<anchor_id>` and provider-ID resolution at build time. Provider aliases are **not copied** into the timestamp database. |
| [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) | AniDB-native timestamp source and aggregator | AniDB regular episodes are projected through AniBridge and verified against one AMDB anchor. Multi-source aggregate rows remain queryable but do not vote in consensus. |
| [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) | Source-addressable timestamp dataset | Stored by Bahamut `videoSn`; no fake MAL/AniList/AMDB identity is invented. |

## Durable AniSkip / Anime Skip API crawling

Two independent 70-requests/minute collectors query **AniSkip v2** (MAL ID
plus series episode) and **Anime Skip GraphQL** (AniList ID plus title episodes).
The crawler's default budget is now **1000 requests per source per run**.

The initial pass can be started once with `mode=bootstrap` and is executed as
**automatically chained bounded workflow runs**, with a default hard safety
limit of 160 runs. On success the daily workflow switches back to ordinary
incremental checks, rechecking positives every 30 days and negatives/errors
after 14 days. AniSkip can now discover later episode candidates from its own
positive results. Unknown episodes beyond the discovery frontier cannot yet
be claimed as exhaustively searched.

**Durable recovery** uses source-specific GitHub branches
`crawler-state-aniskip` and `crawler-state-anime_skip`. These are publicly
readable in a public repo. GitHub Actions caches and uploaded artifacts are
secondary recovery aids, not the primary state database.

API snapshots can be **optionally imported** into `timestamps.db` and
`timestamps-evidence.db` with fully attributed evidence and source lineages,
deduplication, and conservative native episode matching. AniSkip CSV and
API observations share a consensus lineage; unproven Anime Skip/AniList
episode numbers remain source-only. Where an explicit one-to-one AniBridge
mapping independently proves a shared AniDB regular episode, AniList episode
and MAL episode under one AMDB anchor, the builder may add a previously
missing canonical episode or title. No numerical MAL/AniList guesswork,
split/combined mappings or conflicting episode UUIDs are accepted.
**Automatic release import is enabled**: build and release workflows import API
observations as soon as **both** durable source checkpoints exist and validate. Until then, they build from non-API
sources without partial imports. No Actions variable is required. This
maintainer-selected publication setting does not independently grant a license
from upstream providers.

See [the full crawling and release architecture](docs/CRAWLING.md),
[the API data notice](ANIME_SKIP_API_NOTICE.md) and
[the Actions workflow](.github/workflows/crawl.yml). Anime Skip requires
the private `ANIME_SKIP_CLIENT_ID` Actions secret.

Open Anime Timestamps currently declares no explicit repository/data license. The build attributes it, preserves exact snapshot provenance, and includes `OPEN_ANIME_TIMESTAMPS_NOTICE.md` without inventing a license.

## Schema v6: two levels of identity

The core relationship is intentionally simple:

```text
anime-mapping-db
  amdb:<anchor_id>
        |
        v
anime-timestamp-db
  title -> episode -> timestamps
```

`timestamps.db` does not contain a `title_ids` alias table anymore. Its `titles` table is keyed directly by numeric `anchor_id`.

Provider-specific **episode numbering** is still stored because MAL episode 1, AniList episode 1, and AniDB scoped episode 1 are not automatically interchangeable. `episode_ids` therefore uses:

```text
anchor_id + provider + scope + episode_number -> episode_id
```

It does not repeat the provider's title ID. That title ID remains in Anime Mapping DB and is checked there during the build.

Source-native identifiers also appear in `source_title_refs`, `episode_refs`, `source_segments`, and evidence where provenance requires them. The small `source_title_refs` table links an independently verified source-native title key to an AMDB anchor; it does **not** copy the mapping database's global alias graph or claim equivalence between different episode numbering systems.

See [`docs/SCHEMA.md`](docs/SCHEMA.md) for the full contract.

## What the build produces

`timestamps.db` contains two levels of timestamp coverage:

- `segments`: observations normalized to one `amdb:<anchor_id>` and one concrete episode;
- `source_segments`: valid observations whose source episode is known but whose cross-database identity cannot be proven safely.

`timestamps-evidence.db` stores source snapshots, hashes, normalization decisions, votes/scores, and original timing evidence.

Important runtime tables:

- `titles`: AMDB anchor identities, including titles with only source-native episodes;
- `source_title_refs`: exact native-source title keys that resolve to those AMDB anchors (even when episode identity is unresolved);
- `episodes`: normalized playback units under an anchor;
- `episode_ids`: independently proven provider episode numbering/scopes;
- `episode_refs`: timestamp-source episode references;
- `segments`: normalized source observations;
- `source_segments`: unresolved but still queryable source-native ranges; use `source-anchor` or `TimestampResolver.get_source_segments_by_anchor()` to find these via the AMDB title ID, without inventing canonical episode keys;
- `consensus_segments`, `consensus_members`: derived best ranges with exact membership traceability;
- `sources`, `lineages`: source provenance and independent evidence lineage.

All times are stored as integer milliseconds.

## Identity rules

The builder deliberately prefers source-only data over a plausible but wrong normalized identity.

- AniSkip MAL titles must resolve to one stable AMDB anchor before entering normalized runtime.
- SkipDB uses the auditable chain `IMDb -> Anime Mapping DB -> TVDB/TMDB -> AniBridge -> provider episode -> AMDB anchor verification`.
- Open Anime Timestamps uses `AniDB:R -> AniBridge -> provider episode -> AMDB anchor verification`.
- A set of provider IDs must converge on one AMDB anchor. Conflicting anchors suppress normalization instead of merging titles.
- Anime Mapping DB aliases are never copied into runtime just to make lookup convenient.
- Provider episode numbering is stored only when the provider title independently resolves to the same anchor.
- Fractional numeric episode tokens such as `12.5` are preserved rather than truncated.
- AniBridge ratio mappings (`|2`, `|-2`, etc.) are skipped because they represent split/combined episode granularity.
- SkipDB same-season offset inference remains conservative and carries lower mapping confidence.
- Pending/rejected SkipDB rows never enter normalized `segments`.
- Valid rows that cannot prove one anchor/episode remain in `source_segments` instead of being discarded.
- Baha remains source-only until an auditable bulk episode mapping exists.

### Movie normalization

A film can arrive from SkipDB as source episode key `movie` while another source represents the same playback unit as episode `1`.

When both identities exist under the same AMDB anchor, the builder merges local `movie` into canonical `ep:1` before rebuilding episode indexes and consensus. Source references remain intact.

## Consensus

Source observations are never overwritten. `weighted-median-v1` materializes consensus separately and links every consensus row to its exact members.

Consensus weighting includes mapping confidence and uses at most one representative observation per provenance lineage inside a cluster. Mirrors and aggregators therefore cannot multiply one upstream vote. Rows with `consensus_eligible=0` remain queryable but do not vote.

The default boundary tolerance is 5 seconds and is stored in metadata and the manifest.

## Validated schema-v5 coverage

A full real-data schema-v5 validation build on 2026-11-02 passed SQLite integrity checks, foreign-key checks, normalization checks, and consensus membership checks.

It contained:

- **4,151** AMDB-normalized anime titles;
- **57,196** normalized episodes;
- **211,441** normalized source segments;
- **24,072** source-only segments;
- **122,843** materialized consensus segments;
- **181,635** consensus memberships;
- **166,743** provider-specific episode-number entries;
- **105,325** source episode references;
- **276,073** evidence records;
- **310,606** evidence timestamp ranges.

By source in that validated snapshot:

- AniSkip: **76,653** normalized ranges + **10** source-only;
- SkipDB: **37,594** normalized ranges + **1,030** source-only;
- Open Anime Timestamps: **97,194** normalized ranges + **3,351** source-only;
- Baha Anime Skip: **19,681** source-only ranges.

The builder performed **663,497** AMDB identity lookups during the validation build; caching handled **651,515** of them. Only **5** unique provider IDs queried were absent from the mapping database. Provider-ID sets that disagreed on identity were treated conservatively rather than forced together.

Counts are snapshot-dependent. The authoritative numbers for an artifact are always its `manifest.json` and `audit.json`.

## Size impact of schema v6 and compact-v1

Schema v5 removed the duplicated cross-provider title alias layer. Schema v6 adds only compact, explicitly proven native-source title references (not global aliases). The strict staging databases are fully audited before lossless materialization into the read-optimized `compact-v1` distribution layout. The logical table contract is now v6.

On the same validated source snapshot:

| Artifact | v5 staging | compact-v1 | Further reduction |
| --- | ---: | ---: | ---: |
| `timestamps.db` | 68,227,072 B | 49,557,504 B | **27.36%** |
| `timestamps.db.zst` | 19,824,575 B | 13,628,419 B | **31.26%** |
| `timestamps-evidence.db` | 143,065,088 B | 88,813,568 B | **37.92%** |
| `timestamps-evidence.db.zst` | 32,056,175 B | 26,801,955 B | **16.39%** |

The runtime distribution drops build-only reverse indexes and uniqueness B-trees while preserving resolver-critical episode indexes. `segments`, `source_segments`, and `consensus_segments` keep the same public columns and rows.

The evidence distribution dictionary-encodes repeated lineage/status/reason/metadata strings behind a read-only compatibility view named `records`. Existing `SELECT ... FROM records` consumers therefore see the same columns and values, while each repeated value is stored once. `record_segments` remains a normal table with foreign-key validation.

Both the strict staging databases and the final compact distributions must pass SQLite integrity, foreign-key, normalization, and consensus audits. `manifest.json` records the storage profile plus staging and distribution byte sizes.

For the validated `efcedad` build, the complete GitHub Actions artifact (databases, compressed copies, manifest/audit and notices) is 85,512,233 B, down from the previous roughly 148 MB artifact while retaining the same logical schema-v5 contracts.

The slightly smaller normalized coverage versus schema v4 is intentional, not data loss: rows that could not safely converge on one AMDB anchor are retained as source-only observations.

## Evidence and reproducibility

Every downloaded input records:

- original and final URL;
- SHA-256 and byte size;
- retrieval time;
- ETag / Last-Modified when available;
- source role and license note;
- upstream build/version metadata where available.

Anime Mapping DB is consumed as a **build-time bulk artifact**, not through a remote resolver API. The compressed database is hash-addressed in the build cache, decompressed atomically, and checked with SQLite `quick_check` before use.

Schema v5 records the exact mapping artifact hash, mapping schema version, anchor schema version, namespace, and lookup statistics. It does not materialize thousands of redundant mapping-enrichment evidence rows.

AniSkip user identifiers are never copied into compiled artifacts or record hashes. Compatibility with older sanitized schemas explicitly drops `user_id`.

## Actions artifacts and tagged Releases

Normal push, scheduled, and manual database builds use short-lived GitHub Actions artifacts. Permanent GitHub Releases are created only by the dedicated release workflow for an explicit `v*` tag or a manual release run.

A successful database build uploads the runtime/evidence databases, compressed variants, manifest, audit, checksums, and source-specific license/notice files.

GitHub automatically provides **Source code (zip)** and **Source code (tar.gz)** for tagged Releases. The project intentionally does not upload duplicate custom source-code archives; `SHA256SUMS` covers the project-published database and notice assets only.

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

### Native AMDB lookup

The compact database can be queried directly without any provider alias database:

```bash
anime-timestamp-db lookup \
  --db artifacts/timestamps.db \
  --provider amdb \
  --id 18472 \
  --episode 1
```

Python:

```python
from anime_timestamp_db import TimestampResolver

resolver = TimestampResolver("artifacts/timestamps.db")
key = resolver.episode_key("amdb", "18472", 1)
segments = resolver.get_segments_by_anchor("amdb:18472", key) if key else []
consensus = resolver.get_consensus_by_anchor("amdb:18472", key) if key else []
```

### MAL/AniList/AniDB/etc. lookup

Provider title aliases now live only in Anime Mapping DB. Attach its runtime `mappings.db` when convenient compatibility lookup is needed:

```bash
anime-timestamp-db lookup \
  --db artifacts/timestamps.db \
  --mapping-db mappings.db \
  --provider mal \
  --id 5114 \
  --episode 1
```

```python
resolver = TimestampResolver(
    "artifacts/timestamps.db",
    mapping_path="mappings.db",
)
segments = resolver.get_segments_by_episode("mal", "5114", 1)
ids = resolver.title_ids("mal", "5114")
```

This keeps the timestamp artifact compact while preserving convenient external-ID lookup for applications that already use Anime Mapping DB.

### Source-only lookup

Baha and other source-addressable observations can be queried without inventing a normalized title:

```bash
anime-timestamp-db source-lookup \
  --db artifacts/timestamps.db \
  --source baha \
  --episode-key 123456
```

## Audit contract

Every build must pass more than `PRAGMA integrity_check`:

- zero foreign-key errors;
- no invalid timestamp ranges;
- consensus member counts must match their membership table;
- no normalized episode may be left without a runtime segment;
- no anchor may retain both local `movie` and canonical `ep:1` episode identities;
- every provider episode entry must reference an episode under the same AMDB anchor;
- both normalized and source-only real-data coverage must be non-empty;
- evidence records and evidence segments must be non-empty.

The exact results are written to `audit.json` and `manifest.json`.

## File extension

The project uses `timestamps.db` for consistency with `anime-mapping-db` and `mappings.db`. SQLite does not assign meaning to `.db`, `.sqlite`, or `.sqlite3`.

## Licensing

Project code is Apache-2.0. Compiled data follows upstream database terms.

The build includes AniSkip public sanitized data, SkipDB, Baha Anime Skip, AniBridge-derived episode mappings, and stable title identities resolved through Anime Mapping DB. Anime Mapping DB itself is a compiled mapping database with mixed upstream terms, including sources published under ODbL/DbCL and sources with their own attribution/licensing caveats.

Read [`DATA_LICENSE.md`](DATA_LICENSE.md), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and the bundled source-specific notices before redistributing a compiled database.
