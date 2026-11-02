from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from anime_timestamp_db.anibridge import AniBridgeIndex

_SERIES_TITLE_RE = re.compile(r"^(?P<imdb>tt[0-9]+):s(?P<season>[0-9]+)$")
_SERIES_EPISODE_RE = re.compile(r"^e(?P<episode>[0-9]+)$")


@dataclass(slots=True)
class EpisodeIndexStats:
    references: int = 0
    provider_episode_ids: int = 0
    skipped_unmapped: int = 0
    skipped_title_mismatch: int = 0
    conflicts: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "references": self.references,
            "provider_episode_ids": self.provider_episode_ids,
            "skipped_unmapped": self.skipped_unmapped,
            "skipped_title_mismatch": self.skipped_title_mismatch,
            "conflicts": self.conflicts,
        }


def _insert_episode_id(
    conn: sqlite3.Connection,
    *,
    episode_id: int,
    provider: str,
    title_external_id: str,
    episode_number: int,
    scope: str = "",
) -> str:
    normalized_provider = provider.strip().casefold()
    normalized_id = title_external_id.strip()
    normalized_scope = (scope or "").strip().upper()
    number_text = str(int(episode_number))

    title_match = conn.execute(
        """
        SELECT 1
        FROM episodes ep
        JOIN title_ids tid ON tid.title_id=ep.title_id
        WHERE ep.id=? AND tid.provider=? AND tid.external_id=?
        """,
        (episode_id, normalized_provider, normalized_id),
    ).fetchone()
    if title_match is None:
        return "title-mismatch"

    row = conn.execute(
        """
        SELECT episode_id FROM episode_ids
        WHERE provider=? AND title_external_id=? AND scope=?
          AND episode_number_text=?
        """,
        (normalized_provider, normalized_id, normalized_scope, number_text),
    ).fetchone()
    if row is not None:
        return "exists" if int(row[0]) == episode_id else "conflict"

    conn.execute(
        """
        INSERT INTO episode_ids(
            provider, title_external_id, scope, episode_number_text, episode_id
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (normalized_provider, normalized_id, normalized_scope, number_text, episode_id),
    )
    return "inserted"


def rebuild_episode_ids(
    conn: sqlite3.Connection,
    mappings: AniBridgeIndex,
    *,
    source_key: str = "skipdb",
) -> EpisodeIndexStats:
    """Add provider episode IDs derivable from normalized source references.

    This is intentionally additive. Direct providers such as AniSkip may already
    have inserted MAL episode IDs; deleting the table here would destroy valid
    native numbering that AniBridge cannot reconstruct.
    """

    stats = EpisodeIndexStats()
    rows = conn.execute(
        """
        SELECT er.episode_id, er.source_title_key, er.source_episode_key
        FROM episode_refs er
        JOIN sources src ON src.id=er.source_id
        WHERE src.source_key=?
        ORDER BY er.episode_id, er.source_title_key, er.source_episode_key
        """,
        (source_key,),
    ).fetchall()

    for episode_id_raw, title_key_raw, episode_key_raw in rows:
        stats.references += 1
        episode_id = int(episode_id_raw)
        title_key = str(title_key_raw)
        episode_key = str(episode_key_raw)
        targets: list[tuple[str, str, str, int]] = []

        series_title = _SERIES_TITLE_RE.fullmatch(title_key)
        series_episode = _SERIES_EPISODE_RE.fullmatch(episode_key)
        if series_title and series_episode:
            result = mappings.resolve_series_episode(
                series_title.group("imdb"),
                int(series_title.group("season")),
                int(series_episode.group("episode")),
            )
            targets.extend(
                (
                    target.descriptor.provider,
                    target.descriptor.external_id,
                    target.descriptor.scope or "",
                    target.episode_number,
                )
                for target in result.targets
            )
        elif episode_key == "movie" and title_key.startswith("tt"):
            movie_targets = mappings.resolve_movie(title_key)
            targets.extend(
                (target.provider, target.external_id, target.scope or "", 1)
                for target in movie_targets
            )
            targets.append(("imdb_movie", title_key, "", 1))
        else:
            stats.skipped_unmapped += 1
            continue

        if not targets:
            stats.skipped_unmapped += 1
            continue

        seen: set[tuple[str, str, str, int]] = set()
        for provider, external_id, scope, episode_number in targets:
            key = (provider, external_id, scope, episode_number)
            if key in seen:
                continue
            seen.add(key)
            outcome = _insert_episode_id(
                conn,
                episode_id=episode_id,
                provider=provider,
                title_external_id=external_id,
                scope=scope,
                episode_number=episode_number,
            )
            if outcome == "inserted":
                stats.provider_episode_ids += 1
            elif outcome == "title-mismatch":
                stats.skipped_title_mismatch += 1
            elif outcome == "conflict":
                stats.conflicts += 1

    conn.commit()
    return stats
