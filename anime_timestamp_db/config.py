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

BAHA = SourceSpec(
    key="baha",
    display_name="Baha Anime Skip",
    url="https://raw.githubusercontent.com/JacobLinCool/baha-anime-skip/main/packages/baha-anime-skip-db/data.json",
    homepage_url="https://github.com/JacobLinCool/baha-anime-skip",
    source_kind="timestamp",
    license_note="MIT repository license",
)

# Useful, but not part of default public artifacts because the repository does
# not currently expose an explicit license or a comparable upstream statement
# that the snapshot itself is a public dataset/export.
OPEN_ANIME_TIMESTAMPS = SourceSpec(
    key="open-anime-timestamps",
    display_name="Open Anime Timestamps",
    url="https://raw.githubusercontent.com/Ellivers/open-anime-timestamps/master/timestamps.json",
    homepage_url="https://github.com/Ellivers/open-anime-timestamps",
    source_kind="timestamp-marker",
    license_note="No explicit upstream license found; disabled for distributable builds",
    explicit_redistribution_license=False,
)

DEFAULT_BUILD_SOURCES = (ANIBRIDGE, ANISKIP, SKIPDB, BAHA)
SOURCE_BY_KEY = {
    spec.key: spec for spec in (*DEFAULT_BUILD_SOURCES, OPEN_ANIME_TIMESTAMPS)
}
