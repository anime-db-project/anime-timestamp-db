> **AI-assisted project:** Developed with the assistance of AI.

<p align="center">
  <strong>English</strong> · <a href="docs/README.ru.md">Русский</a> · <a href="docs/README.ja.md">日本語</a> · <a href="docs/README.de.md">Deutsch</a> · <a href="docs/README.es.md">Español</a> · <a href="docs/README.fr.md">Français</a> · <a href="docs/README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Releases](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](DATA_LICENSE.md)

A standalone tool and SQLite dataset for anime episode skip intervals: openings, endings, recaps, previews and related segments, with traceable source evidence.

<!-- BEGIN AUTO-GENERATED DATABASE STATS -->
## Database at a glance

**59,072 normalized episodes · 245,952 mapped intervals · 134,975 consensus intervals**

These are separate metrics and must not be added as unique anime or scenes. Source-only observations are accessible but are not counted as normalized episodes.

| Metric | Value |
| --- | ---: |
| AMDB titles with timestamp data | **4,674** |
| Normalized episodes | **59,072** |
| Mapped source intervals | **245,952** |
| Unresolved source-only intervals | **78,381** |
| Consensus intervals | **134,975** |
| Consensus evidence memberships | **216,033** |
| Evidence records | **366,238** |
| Input snapshots | **8** |
| Runtime SQLite size | **66.3 MiB** |
| Compressed SQLite size | **17.0 MiB** |

### Local lookup performance

**Source intervals**

| Metric | Value |
| --- | ---: |
| Median | **0.795 ms** |
| p95 | **0.893 ms** |
| p99 | **1.347 ms** |
| Sequential queries/s | **1,229** |

**Consensus intervals**

| Metric | Value |
| --- | ---: |
| Median | **0.732 ms** |
| p95 | **0.773 ms** |
| p99 | **0.798 ms** |
| Sequential queries/s | **1,357** |

Warm-cache sequential read-only queries on released SQLite, Linux / Python 3.12; 250 sampled episodes × 2 rounds. These are local lookup measurements, not network/API latency.

Release snapshot: **2026-11-14**, [v2026.11.14.30](https://github.com/anime-db-project/anime-timestamp-db/releases/tag/v2026.11.14.30). [Current release manifest](https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/manifest.json).

<!-- END AUTO-GENERATED DATABASE STATS -->

## Features

- Normalize source intervals to anime and episode identities verified by Anime Mapping DB.
- Keep unresolved but valid observations queryable under their original source identifiers.
- Combine independent observations into traceable consensus intervals without counting mirrors as independent votes.
- Publish compact runtime data separately from detailed evidence, audit results and checksums.
- Import supported bulk datasets and maintain checkpointed AniSkip / Anime Skip API collectors.

## Data sources

Bulk builds use public datasets and an Anime Mapping DB snapshot. Two API collectors have durable checkpoints; validated snapshots may be imported by build and release workflows. API credentials and crawler-state details are documented separately.

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — MAL-based bulk timestamp intervals
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — IMDb-linked episode skip data
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — AniDB-linked timestamps and source aggregates
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Bahamut source-native episode intervals
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — episode ID/numbering bridge
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — stable anime identity
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — checkpointed API collection

Normalized records use the shared `amdb:<anchor_id>` identity. Cross-provider episode numbers are accepted only with verified mappings; incompatible or ambiguous observations remain source-only instead of being guessed. [Schema](docs/SCHEMA.md).

## Source coverage and normalization

Timestamp sources vary in title ID systems, episode numbering and depth of coverage. A valid source interval does not automatically prove a matching MAL or AniList episode. The builder distinguishes normalized, source-only and rejected observations instead of fabricating equivalence.

- AniSkip public data: timestamps keyed by MyAnimeList title and episode; only verified AMDB anchors enter normalized records.
- SkipDB: IMDb-based title and episode data; AniBridge and Anime Mapping DB must independently establish the correct anime playback unit.
- Open Anime Timestamps: AniDB-native observations; aggregate records can be kept without adding independent consensus votes.
- Baha Anime Skip: source-specific `videoSn` episodes; these remain source-addressable without invented MAL/AniList episode identities.
- AniSkip and Anime Skip APIs: checkpointed observations can supplement bulk inputs after validation and permission review.

## Identity and episode model

The title namespace is provided by Anime Mapping DB. A normalized title is stored as `anchor_id` and externally represented as `amdb:<anchor_id>`. The timestamp database does not copy the entire mapping graph or its external title aliases. Consumers resolving `mal`, `anilist`, `anidb` and other title IDs should supply `mappings.db` as a separate lookup database.

Episode identity is more specific than title identity. Two services may label different playback units as episode 1; provider, scope and episode number must therefore be explicitly verified. Fractional episodes (such as 12.5), specials and movies are handled without blindly rounding or merging. Split/combined AniBridge ratio mappings are not flattened.

Records that establish a title but not an equivalent numbered episode may be attached to the AMDB anchor through `source_title_refs` and kept as `source_segments`. This preserves discoverability while avoiding a false canonical episode link.

```text
anime-mapping-db (verified amdb:<anchor_id>)
       │
       └── anime-timestamp-db
              titles → episodes → segments
                 │                 │
        source_title_refs        consensus
                 │
            source_segments
```

## Runtime and evidence database schema

`timestamps.db` contains the compact runtime representation used by applications. `titles` holds stable AMDB anchors; `episodes` describes normalized playback units; `episode_ids` stores proven provider-specific numbering; `episode_refs` records original source episode references; `segments` holds accepted normalized source intervals.

`source_segments` keeps valid unresolved intervals. `source_title_refs` records only independently confirmed source-native title references, not every MAL/AniList/etc. ID. `consensus_segments` and `consensus_members` preserve generated ranges and exactly which source observations contributed. `sources` and `lineages` track original dataset identity and independence.

| Table or file | Role |
| --- | --- |
| `titles` | Stable AMDB title identity |
| `episodes` | Verified normalized playback unit |
| `episode_ids` | Proven provider episode numbering |
| `episode_refs` | Original timestamp-source episode keys |
| `segments` | Normalized timestamp observations |
| `source_segments` | Unresolved source-addressable ranges |
| `sources / lineages` | Independent source lineage and provenance |
| `consensus_segments / consensus_members` | Materialized consensus and contributing members |
| `timestamps-evidence.db` | Complete build provenance and decisions |

`timestamps-evidence.db` provides auditable records of input snapshots, hashes, normalization decisions and original timing intervals. Unlike runtime SQLite, it is intended for reproducibility, source attribution and investigation, not ordinary playback queries. All stored time boundaries use integer milliseconds.

## Consensus and provenance

Consensus is materialized separately from original observations. The weighted-median approach groups compatible intervals within a configured boundary tolerance, weights matching confidence and prevents replicas of one original lineage from counting as multiple independent votes. Non-eligible aggregate or uncertain rows remain queryable without influencing consensus.

The default boundary tolerance is 5 seconds; builders may override it through `--consensus-tolerance-ms`. A consensus is a derived proposal, not an assertion that every streaming edition has identical timing. Consumers should inspect source evidence where accuracy is critical.

## Quick start

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Command-line interface

The CLI covers initial schema creation, building, database inspection, audits, lookup and source-native discovery. `lookup` accepts either `--episode` or `--episode-key` and can filter source results or request consensus. When using provider IDs other than `amdb`, attach the matching version of Anime Mapping DB.

```bash
anime-timestamp-db schema-version
anime-timestamp-db inspect --db artifacts/timestamps.db
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1 --consensus
anime-timestamp-db source-anchor --db artifacts/timestamps.db --anchor amdb:18472 --title-refs
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Usage

```bash
# Lookup using the project's stable anime identity
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# For a provider ID, supply the mapping database
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# Source-specific intervals without proven cross-database identity
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Python integration

`TimestampResolver` can access normalized source intervals and consensus by stable anchor or confirmed provider ID. It also supports source-native intervals for records whose episode-level identity cannot be safely normalized. Keep the mapping database alongside the runtime timestamps file if your application needs external anime IDs.

```python
from anime_timestamp_db import TimestampResolver

resolver = TimestampResolver(
    "artifacts/timestamps.db",
    mapping_path="mappings.db",
)

# Known provider title / episode number
segments = resolver.get_segments_by_episode("mal", "5114", 1)

# Verified AMDB identity and concrete episode key
key = resolver.episode_key("amdb", "18472", 1)
consensus = resolver.get_consensus_by_anchor("amdb:18472", key) if key else []
```

## Practical ways to use the database

You can use the published SQLite file without running the crawlers, an API key, or the build pipeline. Choose a method that suits your product:

- **Video players.** Show optional skip-opening, skip-ending, recap or preview actions for an episode when matching data exists.
- **Anime websites and catalogues.** Display episode timeline annotations, provenance and cross-source agreement.
- **Bots and applications.** Resolve a title by AMDB or confirmed MAL/AniList/AniDB ID and fetch source-specific or consensus ranges.
- **Offline or mobile tools.** Bundle a compatible SQLite snapshot for local, read-only lookups without runtime calls to upstream APIs.
- **Auditing and data research.** Compare individual observations, source-only coverage and consensus; inspect the evidence database for provenance.

Download the existing release databases. For AMDB IDs alone, `timestamps.db` is sufficient; to look up MAL/AniList/etc. title IDs, also download a compatible `mappings.db`:

```bash
curl -fL -o timestamps.db \
  https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/timestamps.db
curl -fL -o mappings.db \
  https://github.com/anime-db-project/anime-mapping-db/releases/latest/download/mappings.db
```

Use the packaged `TimestampResolver` (`python -m pip install -e .` in the cloned timestamp repository). It returns source-specific segments and consensus independently:

```python
from anime_timestamp_db import TimestampResolver

resolver = TimestampResolver("timestamps.db", mapping_path="mappings.db")

# Use a verified MAL title ID and its own episode numbering.
segments = resolver.get_segments_by_episode("mal", "5114", 1)
key = resolver.episode_key("mal", "5114", 1)
consensus = resolver.get_consensus("mal", "5114", key) if key else []

for segment in segments:
    print(segment.segment_type, segment.start_ms / 1000, segment.end_ms / 1000)
for segment in consensus:
    print("consensus", segment.segment_type, segment.start_ms, segment.end_ms)
```

SQLite can also be used directly from any language with a SQLite driver. This read-only SQL example fetches normalized intervals by AMDB anchor and episode key:

```python
import sqlite3

with sqlite3.connect("file:timestamps.db?mode=ro", uri=True) as db:
    intervals = db.execute("""
        SELECT ep.episode_key, seg.segment_type, seg.start_ms,
               seg.end_ms, src.source_key
        FROM episodes AS ep
        JOIN segments AS seg ON seg.episode_id = ep.id
        JOIN sources AS src ON src.id = seg.source_id
        WHERE ep.anchor_id = ? AND ep.episode_key = ?
        ORDER BY seg.start_ms
    """, (18472, "ep:1")).fetchall()

for interval in intervals:
    print(interval)
```

Replace the illustrative anchor and episode with IDs that actually exist in your chosen snapshot. `start_ms` and `end_ms` are **integer milliseconds**, so divide by 1,000 only when your player needs seconds. A title present in Anime Mapping DB does not necessarily have any timestamp entries.

Unresolved observations can still be inspected using `source-lookup` or `source-anchor`; do not interpret a source's episode key as a confirmed MAL/AniList episode number.

```bash
anime-timestamp-db source-anchor --db timestamps.db --anchor amdb:18472
anime-timestamp-db source-lookup --db timestamps.db --source baha --episode-key 123456
```

Use the release manifests and SHA-256 checksums to pin compatible database versions. The timestamp release records the exact mapping database hash used during its build; mismatched snapshots may produce missed lookups or anchor redirects.

## Additional external timestamp providers

Optional crawlers and source-only checkpoint importers are available for
[IntroDB](https://introdb.app/),
[PublicMetaDB](https://publicmetadb.com/),
[TheIntroDB](https://theintrodb.org/) and
[IntroHater](https://introhater.com/). These community providers are
acknowledged with official links and thanks to their contributors, **not
represented as official sponsors or contributors to this repository**.
Attribution alone is not permission to collect or redistribute their data.

Every provider has its own request budget, per-second/minute/hour rate limits
and polite randomized load spacing. HTTP 429 is retried once within the
server's retry window; a further 429 ends the job, preserving collected
checkpoints. IntroDB and IntroHater automated bulk jobs require explicit
permission from their owners. PublicMetaDB uses a private API key. New source
checkpoint data is only imported into released SQLite files after separate
source-specific permission approval. Imported external episodes stay
source-only unless independently proven.

See [external source setup](docs/EXTERNAL_API_SOURCES.md) and
[provider acknowledgment and rights](EXTERNAL_SOURCES_NOTICE.md).

## API collection and release imports

Two separate collectors query AniSkip v2 (MAL/episode) and Anime Skip GraphQL (AniList/title episodes). They are rate-limited, checkpointable and can resume after interrupted runs. The crawler does not infer coverage of undiscovered episodes from a successful response about earlier episodes.

Public checkpoint branches (`crawler-state-aniskip`, `crawler-state-anime_skip`) preserve normalized source state across GitHub Actions jobs. Valid snapshots are imported by release/build workflows only when both source checkpoints are available and pass validation; partial or unverified snapshots are not combined with a release.

Anime Skip collection uses a private `ANIME_SKIP_CLIENT_ID` secret. API access does not by itself confer redistribution rights. Local importing requires explicit operator confirmation through `--allow-api-redistribution` along with `--api-checkpoint-dir`; read source-specific notices first.

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --api-checkpoint-dir checkpoints \
  --allow-api-redistribution
```

## Database and releases

Permanent downloads are published in GitHub Releases (tags or manual release runs). Each release contains `timestamps.db`, `timestamps-evidence.db`, compressed copies, `manifest.json`, `audit.json`, `SHA256SUMS`, benchmark results and required notices.

- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

This project is independent of **anime-db-bot** and is not required by the bot. Its schema, input coverage and upstream usage terms should be checked before integration or redistribution.

## Distribution files

GitHub Releases are the supported download channel. The compact runtime SQLite is distributed separately from evidence. `manifest.json` records source versions, mapping identity, schema and sizes; `audit.json` contains validation results and `performance.json` records repeatable local lookup measurements.

| Table or file | Role |
| --- | --- |
| `timestamps.db` | Compact read-only runtime SQLite |
| `timestamps-evidence.db` | Detailed provenance SQLite |
| `*.db.zst` | Compressed distributions |
| `manifest.json` | Build inputs, versions, sizes and checksums |
| `audit.json` | Audit and integrity results |
| `SHA256SUMS` | SHA-256 checksum list |
| `DATA_LICENSE.md / THIRD_PARTY_NOTICES.md` | Upstream attribution and license notices |

## Auditing and reproducibility

Every build is checked for SQLite integrity and foreign-key consistency, valid nonnegative intervals, valid episode and title references, consensus membership consistency and non-empty coverage. Validation covers both the strict staging databases and compact distributions; rejected/unknown matches should never leak into normalized segments.

Input snapshot URLs, checksums, sizes and retrieval metadata are recorded. The build reads a pinned, checked Anime Mapping DB artifact locally. Accurate dataset counts and sizes belong in the current manifest rather than fixed README metrics.

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## Integration boundaries

This project is a standalone timestamp dataset, not a mandatory dependency of anime-db-bot. It does not query streaming sites during normal database builds, does not promise that a title has skip data, and does not make unsafe season or episode matches to maximize reported coverage.

## Documentation

- [Schema and resolver contract](docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](docs/CRAWLING.md)
- [API source notice](ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](DATA_LICENSE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)

## License and attribution

Code: Apache-2.0. Compiled data is subject to upstream dataset and API terms. Some sources have special attribution or no explicit published data license; consult the notices before redistributing compiled artifacts. [Apache-2.0](LICENSE) · [DATA_LICENSE.md](DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
