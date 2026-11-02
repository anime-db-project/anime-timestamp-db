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
    redistributable: bool = True


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

# This dataset is useful but the upstream repository does not currently expose
# a license. The importer is deliberately not part of the default public build.
OPEN_ANIME_TIMESTAMPS = SourceSpec(
    key="open-anime-timestamps",
    display_name="Open Anime Timestamps",
    url="https://raw.githubusercontent.com/Ellivers/open-anime-timestamps/master/timestamps.json",
    homepage_url="https://github.com/Ellivers/open-anime-timestamps",
    source_kind="timestamp-marker",
    license_note="No explicit upstream license found; disabled for distributable builds",
    redistributable=False,
)

DEFAULT_BUILD_SOURCES = (ANIBRIDGE, SKIPDB, BAHA)
SOURCE_BY_KEY = {spec.key: spec for spec in (*DEFAULT_BUILD_SOURCES, OPEN_ANIME_TIMESTAMPS)}
