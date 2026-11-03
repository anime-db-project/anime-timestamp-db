# Compiled data licensing

The software in this repository is Apache-2.0. Compiled timestamp databases are governed separately by the terms and publication status of their upstream datasets.

## AniSkip public sanitized dataset

The default build incorporates the official `aniskip/sanitize-db-dump/skip_times_public.csv` export. Upstream publishes this as a public/sanitized dataset and uses the sanitized snapshot for database seeding, but the dump repository does not currently expose a separate explicit data license.

We do not label AniSkip data as MIT, ODbL, or any other license without an upstream grant. See `ANISKIP_PUBLIC_DATA_NOTICE.md`. The manifest records the exact source URL and SHA-256 used for each build. AniSkip `user_id` values are not copied into the compiled databases or record hashes.

## SkipDB-derived data

The default build incorporates SkipDB data. SkipDB publishes its database under ODbL 1.0 and also attaches additional Service Provider Reciprocity terms.

A distributable build therefore carries `SKIPDB_DATA_LICENSE.txt`, an unchanged copy of SkipDB's upstream `DATA-LICENSE`. Treat that file as part of the compiled database's required licensing material. The build manifest also records the exact SkipDB source URL and SHA-256 of the downloaded dump used for the build.

Attribution: SkipDB — https://skipdb.tv/

ODbL 1.0: https://opendatacommons.org/licenses/odbl/1-0/

Upstream terms: https://github.com/SkipDB-TV/skipdb/blob/main/DATA-LICENSE

## Anime Mapping DB-derived title aliases

The builder consumes the latest published `anime-db-project/anime-mapping-db` runtime database and copies only direct, accepted, conflict-free title aliases for MAL titles already present in the timestamp database.

Anime Mapping DB is itself a compiled database assembled from multiple independent upstream datasets. Its Apache-2.0 software license does **not** automatically relicense the mapping data. The generated mapping database can contain data subject to ODbL 1.0 + DbCL 1.0, CC0, permissive repository licenses, attribution requirements, and sources for which no standalone dataset license is declared.

Every timestamp artifact therefore includes:

- `MAPPING_DB_DATA_LICENSE.md`;
- `MAPPING_DB_THIRD_PARTY_NOTICES.md`.

Those files are copied from the Anime Mapping DB repository and describe its data-licensing boundary and current source-by-source notices. Redistribution of a timestamp database containing those derived aliases must preserve and comply with the applicable upstream terms.

The timestamp builder does not use the mapping database to infer provider episode numbering. It copies title identity only.

## Baha Anime Skip

The builder consumes the checked-in Baha Anime Skip database from `JacobLinCool/baha-anime-skip`. The upstream repository is MIT-licensed. `BAHA_LICENSE.txt` is included with database artifacts.

## AniBridge

AniBridge's published mapping file is used at build time to establish safe episode identities. The AniBridge repository is MIT-licensed; `ANIBRIDGE_LICENSE.txt` is included with artifacts. AniBridge's mapping payload itself aggregates upstream mapping sources, so its own provenance documentation should also be consulted for downstream redistribution decisions.

## Open Anime Timestamps

The default build incorporates the public `Ellivers/open-anime-timestamps/timestamps.json` database. Upstream does not currently declare an explicit repository or standalone data license, so Anime Timestamp DB does not invent one. Attribution and exact snapshot provenance are preserved and every artifact includes `OPEN_ANIME_TIMESTAMPS_NOTICE.md`.

The upstream file is also an aggregator. Its record-level `sources` metadata is retained so republished AniSkip/Anime Skip/BetterVRV data is not presented as original Open Anime Timestamps evidence. Multi-source aggregate records remain queryable but are excluded from consensus voting because field-level provenance is not available.

If upstream publishes or changes licensing terms, subsequent builds and redistribution notices must be updated to comply with those terms.

## Live AniSkip / Anime Skip API checkpoints

Live API observations are optional and different from the default public
AniSkip CSV and Open Anime Timestamps snapshot sources. The API's availability
and the server project's open-source software license do **not** automatically
establish independent rights to redistribute the underlying crowdsourced data.
Anime Skip also mirrors other upstream data such as BetterVRV.

The maintainer has enabled automatic imports once **both** valid API
checkpoints are available. Build and release workflows pass the required
`--allow-api-redistribution` flag together with the checkpoint directory
only in that case; incomplete sources do not create a partial API-data
release. Every enabled build includes `ANIME_SKIP_API_NOTICE.md`, exact
checkpoint checksums, source-native identifiers, and lineage preservation.
Unknown/ambiguous episode matches remain source-addressable.

**Important:** the separate durable checkpoint branches contain live API
data and are publicly readable if this repository is public; verify applicable
terms before starting a long-term public bootstrap crawl.

## Build provenance

Every build records source URLs, final redirected URLs, retrieval timestamps, hashes, byte sizes, ETag/Last-Modified values when available, source roles, and license notes in `manifest.json` and/or `timestamps-evidence.db`.

The manifest also records the exact Anime Mapping DB release redirect/hash, mapping schema metadata, how many aliases were added, and how many mapping/local conflicts were suppressed.
