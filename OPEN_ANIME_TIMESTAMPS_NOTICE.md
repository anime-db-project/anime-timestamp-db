# Open Anime Timestamps data notice

Source: https://github.com/Ellivers/open-anime-timestamps

Anime Timestamp DB consumes the upstream `timestamps.json` snapshot as a timestamp source. The file is keyed by AniDB title ID and includes episode-level opening, ending, recap, preview-start, and provenance metadata.

At the time of integration, the upstream repository does not declare an explicit repository or standalone data license. Anime Timestamp DB therefore does not assign Open Anime Timestamps data an invented SPDX/data license. Instead, every build preserves the source URL, final download URL, retrieval time, SHA-256, byte size, and this notice.

If upstream publishes or changes licensing/redistribution terms, future builds and notices must be updated to follow the then-current upstream terms.

## Provenance handling

Open Anime Timestamps can aggregate several origins in one episode record. The upstream `sources` array is preserved in evidence metadata.

Single-source records use the corresponding provenance lineage (`open-anime-timestamps`, `open-anime-timestamps-chapter-data`, `aniskip`, `anime-skip`, or `better-vrv`). Multi-source records are stored under `open-anime-timestamps-aggregate` because upstream provenance is record-level rather than field-level; these ranges remain queryable but are excluded from consensus voting to avoid manufacturing an independent vote.

Point-only `preview_start` values have no upstream end boundary. They are retained in evidence metadata rather than converted into invented skip ranges.
