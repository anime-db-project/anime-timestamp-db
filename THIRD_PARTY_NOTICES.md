# Third-party notices

Anime Timestamp DB's code license does not replace upstream data or software licenses.

## AniSkip public dataset

Source: https://github.com/aniskip/sanitize-db-dump

Used as the primary MAL-native timestamp source. AniSkip's current public sanitized CSV exposes MAL title ID (`anime_id`), episode number, media provider, segment type/range, votes, episode length, and submission date. The importer also remains compatible with the older sanitized export schema. User identifiers are never copied into compiled artifacts.

Upstream publishes the snapshot as public/sanitized data and uses it for database seeding, but no separate explicit data license was found in the dump repository. See `ANISKIP_PUBLIC_DATA_NOTICE.md`.

## SkipDB

Source: https://github.com/SkipDB-TV/skipdb

Used as a supplementary timestamp dataset. Only approved rows with a safe anime episode mapping enter runtime `segments`; other public statuses are retained only in the evidence database. SkipDB contributor identifiers are not copied into the compiled databases.

Data terms: ODbL 1.0 plus SkipDB's additional Service Provider Reciprocity terms. See `SKIPDB_DATA_LICENSE.txt` in every build artifact.

## AniBridge Mappings

Source: https://github.com/anibridge/anibridge-mappings

MIT License, copyright © 2026 AniBridge.

Used only as a build-time episode identity bridge for SkipDB. Ratio/split mappings are rejected rather than projected onto differently cut episodes.

## Anime Mapping DB

Source: https://github.com/anime-db-project/anime-mapping-db

Used as a build-time **title identity enrichment** source. The builder downloads the published `mappings.db.zst` artifact and accepts only one-hop edges with `status='accepted'` where the MAL source node has no directional conflict for the target provider.

No transitive graph walk is performed. A title alias does not create provider episode numbering. An alias already attached to a different local title is suppressed instead of merging the titles.

Anime Mapping DB is a compiled database with mixed upstream licensing/provenance. Its current data licensing notice and third-party source table are included in every timestamp artifact as:

- `MAPPING_DB_DATA_LICENSE.md`;
- `MAPPING_DB_THIRD_PARTY_NOTICES.md`.

Those notices include sources under ODbL/DbCL, CC0, permissive repository licenses, and public datasets without a clearly declared standalone data license. Preserve and review the applicable terms before redistributing a compiled timestamp database.

## Baha Anime Skip

Source: https://github.com/JacobLinCool/baha-anime-skip

MIT License, copyright © 2022 JacobLinCool.

The builder consumes `packages/baha-anime-skip-db/data.json`. Because that bulk file is keyed by Bahamut episode `videoSn` and does not carry a reusable cross-database episode mapping, its ranges remain source-addressable rather than being assigned guessed MAL/AniList/AniDB IDs.

## open-anime-timestamps

Reviewed source/fork: https://github.com/Ellivers/open-anime-timestamps

Not included in default builds because an explicit repository license or equivalent upstream public-dataset statement was not found during integration review.
