# Third-party notices

Anime Timestamp DB's code license does not replace upstream data or software licenses.

## SkipDB

Source: https://github.com/SkipDB-TV/skipdb

Used as the principal normalized timestamp dataset. Only approved rows with a safe anime episode mapping enter runtime `segments`; other public statuses are retained only in the evidence database. SkipDB contributor identifiers are not copied into the compiled databases.

Data terms: ODbL 1.0 plus SkipDB's additional Service Provider Reciprocity terms. See `SKIPDB_DATA_LICENSE.txt` in every build artifact.

## AniBridge Mappings

Source: https://github.com/anibridge/anibridge-mappings

MIT License, copyright © 2026 AniBridge.

Used only as a build-time episode identity bridge. Ratio/split mappings are rejected rather than projected onto differently cut episodes.

## Baha Anime Skip

Source: https://github.com/JacobLinCool/baha-anime-skip

MIT License, copyright © 2022 JacobLinCool.

The builder consumes `packages/baha-anime-skip-db/data.json`. Because that bulk file is keyed by Bahamut episode `videoSn` and does not carry a reusable cross-database episode mapping, its ranges remain source-addressable rather than being assigned guessed MAL/AniList/AniDB IDs.

## open-anime-timestamps

Reviewed source/fork: https://github.com/Ellivers/open-anime-timestamps

Not included in default distributable builds because an explicit repository license was not found during integration review.
