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

## Excluded sources

Public downloadability by itself is not treated as redistribution permission. `open-anime-timestamps` remains excluded because no explicit upstream license or equivalent public-dataset statement was found during integration.

## Build provenance

Every build records source URLs, final redirected URLs, retrieval timestamps, hashes, byte sizes, ETag/Last-Modified values when available, source roles, and license notes in `manifest.json` and/or `timestamps-evidence.db`.

The manifest also records the exact Anime Mapping DB release redirect/hash, mapping schema metadata, how many aliases were added, and how many mapping/local conflicts were suppressed.
