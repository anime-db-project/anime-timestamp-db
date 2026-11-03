from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceSpec:
    key: str
    display_name: str
    url: str
    homepage_url: str
    source_kind: str
    license_note: str
    explicit_redistribution_license: bool = True


ANISKIP = SourceSpec(
    key="aniskip",
    display_name="AniSkip Public Dataset",
    url="https://raw.githubusercontent.com/aniskip/sanitize-db-dump/main/skip_times_public.csv",
    homepage_url="https://github.com/aniskip/sanitize-db-dump",
    source_kind="timestamp",
    license_note=(
        "Official public sanitized AniSkip dataset; upstream publishes it for "
        "dataset export/seeding but no separate explicit data license was found"
    ),
    explicit_redistribution_license=False,
)

ANISKIP_API = SourceSpec(
    key="aniskip-api",
    display_name="AniSkip Live API",
    url=(
        "https://raw.githubusercontent.com/anime-db-project/anime-timestamp-db/"
        "crawler-state-aniskip/checkpoints/aniskip.json.gz"
    ),
    homepage_url="https://api.aniskip.com/api-docs",
    source_kind="timestamp",
    license_note=(
        "Live AniSkip API data. No independent explicit bulk redistribution "
        "grant confirmed; release inclusion requires operator approval."
    ),
    explicit_redistribution_license=False,
)

ANIME_SKIP_API = SourceSpec(
    key="anime-skip-api",
    display_name="Anime Skip Live API",
    url=(
        "https://raw.githubusercontent.com/anime-db-project/anime-timestamp-db/"
        "crawler-state-anime_skip/checkpoints/anime_skip.json.gz"
    ),
    homepage_url="https://anime-skip.com/",
    source_kind="timestamp",
    license_note=(
        "Anime Skip API and mirrored upstream lineages. Open-source API code "
        "license is not an independent grant for data redistribution. "
        "Release inclusion requires operator approval."
    ),
    explicit_redistribution_license=False,
)


SKIPDB = SourceSpec(
    key="skipdb",
    display_name="SkipDB",
    url="https://github.com/SkipDB-TV/skipdb/releases/latest/download/skipdb-dump.json",
    homepage_url="https://skipdb.tv/",
    source_kind="timestamp",
    license_note="ODbL 1.0 + SkipDB Service Provider Reciprocity",
)

ANIBRIDGE = SourceSpec(
    key="anibridge",
    display_name="AniBridge Mappings",
    url="https://github.com/anibridge/anibridge-mappings/releases/download/v3/mappings.min.json",
    homepage_url="https://mappings.anibridge.eliasbenb.dev/",
    source_kind="mapping",
    license_note="MIT; mapping payload aggregates upstream mapping sources",
)

ANIME_MAPPING_DB = SourceSpec(
    key="anime-mapping-db",
    display_name="Anime Mapping DB",
    url=(
        "https://github.com/anime-db-project/anime-mapping-db/"
        "releases/latest/download/mappings.db.zst"
    ),
    homepage_url="https://github.com/anime-db-project/anime-mapping-db",
    source_kind="mapping",
    license_note=(
        "Compiled direct title mappings with mixed upstream data terms; "
        "see bundled MAPPING_DB_DATA_LICENSE.md and "
        "MAPPING_DB_THIRD_PARTY_NOTICES.md"
    ),
    explicit_redistribution_license=False,
)

BAHA = SourceSpec(
    key="baha",
    display_name="Baha Anime Skip",
    url="https://raw.githubusercontent.com/JacobLinCool/baha-anime-skip/main/packages/baha-anime-skip-db/data.json",
    homepage_url="https://github.com/JacobLinCool/baha-anime-skip",
    source_kind="timestamp",
    license_note="MIT repository license",
)

OPEN_ANIME_TIMESTAMPS = SourceSpec(
    key="open-anime-timestamps",
    display_name="Open Anime Timestamps",
    url="https://raw.githubusercontent.com/Ellivers/open-anime-timestamps/master/timestamps.json",
    homepage_url="https://github.com/Ellivers/open-anime-timestamps",
    source_kind="timestamp",
    license_note=(
        "Public upstream timestamp database; no explicit repository/data license "
        "is currently declared. Attribution and exact snapshot provenance are preserved."
    ),
    explicit_redistribution_license=False,
)

DEFAULT_BUILD_SOURCES = (
    ANIBRIDGE,
    ANIME_MAPPING_DB,
    ANISKIP,
    SKIPDB,
    OPEN_ANIME_TIMESTAMPS,
    BAHA,
)
SOURCE_BY_KEY = {spec.key: spec for spec in DEFAULT_BUILD_SOURCES}
