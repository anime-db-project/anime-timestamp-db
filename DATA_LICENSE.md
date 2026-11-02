# Compiled data licensing

The software in this repository is Apache-2.0. The compiled timestamp databases are governed separately by the terms of the upstream datasets included in a build.

## SkipDB-derived data

The default build incorporates SkipDB data. SkipDB publishes its database under ODbL 1.0 and also attaches additional Service Provider Reciprocity terms.

A distributable build therefore carries `SKIPDB_DATA_LICENSE.txt`, an unchanged copy of SkipDB's upstream `DATA-LICENSE`. Treat that file as part of the compiled database's required licensing material. The build manifest also records the exact SkipDB source URL and SHA-256 of the downloaded dump used for the build.

Attribution: SkipDB — https://skipdb.tv/

ODbL 1.0: https://opendatacommons.org/licenses/odbl/1-0/

Upstream terms: https://github.com/SkipDB-TV/skipdb/blob/main/DATA-LICENSE

## Baha Anime Skip

The builder consumes the checked-in Baha Anime Skip database from `JacobLinCool/baha-anime-skip`. The upstream repository is MIT-licensed. `BAHA_LICENSE.txt` is included with database artifacts.

## AniBridge

AniBridge's published mapping file is used at build time to establish safe episode identities. The AniBridge repository is MIT-licensed; `ANIBRIDGE_LICENSE.txt` is included with artifacts. AniBridge's mapping payload itself aggregates upstream mapping sources, so its own provenance documentation should also be consulted for downstream redistribution decisions.

## Excluded sources

Public downloadability is not treated as redistribution permission. `open-anime-timestamps` is excluded from the default distributable build because no explicit upstream license was found during integration.

## Build provenance

Every build records source URLs, final redirected URLs, retrieval timestamps, hashes, byte sizes, ETag/Last-Modified values when available, source roles, and license notes in `manifest.json` and/or `timestamps-evidence.db`.
