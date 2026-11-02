from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class NormalizationStats:
    movie_episode_merges: int = 0
    episode_refs_repointed: int = 0
    segments_repointed: int = 0
    episode_ids_repointed: int = 0
    durations_filled: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def merge_movie_episode_aliases(conn: sqlite3.Connection) -> NormalizationStats:
    """Merge a source-local ``movie`` episode into ``ep:1`` for one AMDB title."""

    stats = NormalizationStats()
    pairs = conn.execute(
        """
        SELECT
            movie.id,
            regular.id,
            movie.duration_ms,
            regular.duration_ms
        FROM episodes AS movie
        JOIN episodes AS regular
          ON regular.anchor_id=movie.anchor_id
         AND regular.episode_key='ep:1'
        WHERE movie.episode_key='movie'
        ORDER BY movie.id
        """
    ).fetchall()

    for movie_id_raw, regular_id_raw, movie_duration, regular_duration in pairs:
        movie_id = int(movie_id_raw)
        regular_id = int(regular_id_raw)

        if regular_duration is None and movie_duration is not None:
            conn.execute(
                "UPDATE episodes SET duration_ms=? WHERE id=?",
                (int(movie_duration), regular_id),
            )
            stats.durations_filled += 1

        cursor = conn.execute(
            "UPDATE episode_refs SET episode_id=? WHERE episode_id=?",
            (regular_id, movie_id),
        )
        stats.episode_refs_repointed += max(0, int(cursor.rowcount))

        cursor = conn.execute(
            "UPDATE segments SET episode_id=? WHERE episode_id=?",
            (regular_id, movie_id),
        )
        stats.segments_repointed += max(0, int(cursor.rowcount))

        cursor = conn.execute(
            "UPDATE episode_ids SET episode_id=? WHERE episode_id=?",
            (regular_id, movie_id),
        )
        stats.episode_ids_repointed += max(0, int(cursor.rowcount))

        conn.execute("DELETE FROM episodes WHERE id=?", (movie_id,))
        stats.movie_episode_merges += 1

    conn.commit()
    return stats
