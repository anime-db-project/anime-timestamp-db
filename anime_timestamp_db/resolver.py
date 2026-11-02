from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from anime_timestamp_db.database import connect_readonly


def _episode_number_text(value: int | float | str) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


@dataclass(frozen=True, slots=True)
class Segment:
    segment_type: str
    start_ms: int
    end_ms: int
    source: str
    lineage: str
    source_segment_id: str
    media_duration_ms: int | None
    quality_score: float | None
    mapping_method: str
    mapping_confidence: float
    votes_up: int
    votes_down: int


@dataclass(frozen=True, slots=True)
class SourceSegment:
    segment_type: str
    start_ms: int
    end_ms: int
    source: str
    lineage: str
    source_title_key: str
    source_episode_key: str
    source_segment_id: str
    media_duration_ms: int | None


@dataclass(frozen=True, slots=True)
class ConsensusSegment:
    segment_type: str
    cluster_index: int
    start_ms: int
    end_ms: int
    media_duration_ms: int | None
    member_count: int
    source_count: int
    lineage_count: int
    confidence: float
    algorithm: str
    tolerance_ms: int


class TimestampResolver:
    """Read-only resolver for a published runtime timestamp database."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        return connect_readonly(self.path)

    def title_ids(self, provider: str, external_id: str) -> dict[str, list[str]]:
        provider = str(provider).strip().casefold()
        external_id = str(external_id).strip()
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT title_id FROM title_ids WHERE provider=? AND external_id=?",
                (provider, external_id),
            ).fetchone()
            if row is None:
                return {}
            result: dict[str, list[str]] = {}
            for item in conn.execute(
                """
                SELECT provider, external_id FROM title_ids
                WHERE title_id=? ORDER BY provider, external_id
                """,
                (int(row[0]),),
            ):
                result.setdefault(str(item[0]), []).append(str(item[1]))
            return result

    def episode_key(
        self,
        provider: str,
        external_id: str,
        episode_number: int | float | str,
        *,
        scope: str | None = None,
    ) -> str | None:
        normalized_provider = str(provider).strip().casefold()
        normalized_id = str(external_id).strip()
        number_text = _episode_number_text(episode_number)
        with closing(self._connect()) as conn:
            if scope is None:
                rows = conn.execute(
                    """
                    SELECT DISTINCT ep.episode_key
                    FROM episode_ids eid
                    JOIN episodes ep ON ep.id=eid.episode_id
                    WHERE eid.provider=? AND eid.title_external_id=?
                      AND eid.episode_number_text=?
                    ORDER BY ep.episode_key
                    """,
                    (normalized_provider, normalized_id, number_text),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT ep.episode_key
                    FROM episode_ids eid
                    JOIN episodes ep ON ep.id=eid.episode_id
                    WHERE eid.provider=? AND eid.title_external_id=?
                      AND eid.scope=? AND eid.episode_number_text=?
                    ORDER BY ep.episode_key
                    """,
                    (
                        normalized_provider,
                        normalized_id,
                        str(scope).strip().upper(),
                        number_text,
                    ),
                ).fetchall()
            if len(rows) != 1:
                return None
            return str(rows[0][0])

    def get_segments(
        self,
        provider: str,
        external_id: str,
        episode_key: str,
        *,
        source: str | None = None,
        media_duration_ms: int | None = None,
    ) -> list[Segment]:
        where_params: list[object] = [
            str(provider).strip().casefold(),
            str(external_id).strip(),
            str(episode_key).strip(),
        ]
        source_sql = ""
        if source is not None:
            source_sql = " AND src.source_key=?"
            where_params.append(str(source).strip().casefold())

        if media_duration_ms is None:
            distance_select = "0 AS duration_distance"
            params = where_params
        else:
            distance_select = (
                "ABS(COALESCE(seg.media_duration_ms, ?) - ?) AS duration_distance"
            )
            params = [media_duration_ms, media_duration_ms, *where_params]

        query = f"""
            SELECT seg.segment_type, seg.start_ms, seg.end_ms,
                   src.source_key, lin.lineage_key, seg.source_segment_id,
                   seg.media_duration_ms, seg.quality_score,
                   seg.mapping_method, seg.mapping_confidence,
                   seg.votes_up, seg.votes_down, {distance_select}
            FROM title_ids tid
            JOIN episodes ep ON ep.title_id=tid.title_id
            JOIN segments seg ON seg.episode_id=ep.id
            JOIN sources src ON src.id=seg.source_id
            JOIN lineages lin ON lin.id=seg.lineage_id
            WHERE tid.provider=? AND tid.external_id=? AND ep.episode_key=?
              {source_sql}
            ORDER BY duration_distance, seg.segment_type, seg.start_ms, seg.end_ms,
                     seg.quality_score DESC, seg.votes_up DESC
        """
        with closing(self._connect()) as conn:
            return [
                Segment(
                    segment_type=str(row[0]),
                    start_ms=int(row[1]),
                    end_ms=int(row[2]),
                    source=str(row[3]),
                    lineage=str(row[4]),
                    source_segment_id=str(row[5]),
                    media_duration_ms=int(row[6]) if row[6] is not None else None,
                    quality_score=float(row[7]) if row[7] is not None else None,
                    mapping_method=str(row[8]),
                    mapping_confidence=float(row[9]),
                    votes_up=int(row[10]),
                    votes_down=int(row[11]),
                )
                for row in conn.execute(query, tuple(params))
            ]

    def get_segments_by_episode(
        self,
        provider: str,
        external_id: str,
        episode_number: int | float | str,
        *,
        scope: str | None = None,
        **kwargs: object,
    ) -> list[Segment]:
        key = self.episode_key(provider, external_id, episode_number, scope=scope)
        if key is None:
            return []
        return self.get_segments(provider, external_id, key, **kwargs)

    def get_consensus(
        self,
        provider: str,
        external_id: str,
        episode_key: str,
        *,
        media_duration_ms: int | None = None,
    ) -> list[ConsensusSegment]:
        if media_duration_ms is None:
            distance_select = "0 AS duration_distance"
            params: list[object] = [
                str(provider).strip().casefold(),
                str(external_id).strip(),
                str(episode_key).strip(),
            ]
        else:
            distance_select = (
                "ABS(COALESCE(c.media_duration_ms, ?) - ?) AS duration_distance"
            )
            params = [
                media_duration_ms,
                media_duration_ms,
                str(provider).strip().casefold(),
                str(external_id).strip(),
                str(episode_key).strip(),
            ]
        query = f"""
            SELECT c.segment_type, c.cluster_index, c.start_ms, c.end_ms,
                   c.media_duration_ms, c.member_count, c.source_count,
                   c.lineage_count, c.confidence, c.algorithm, c.tolerance_ms,
                   {distance_select}
            FROM title_ids tid
            JOIN episodes ep ON ep.title_id=tid.title_id
            JOIN consensus_segments c ON c.episode_id=ep.id
            WHERE tid.provider=? AND tid.external_id=? AND ep.episode_key=?
            ORDER BY duration_distance, c.confidence DESC, c.member_count DESC,
                     c.segment_type, c.start_ms, c.cluster_index
        """
        with closing(self._connect()) as conn:
            return [
                ConsensusSegment(
                    segment_type=str(row[0]),
                    cluster_index=int(row[1]),
                    start_ms=int(row[2]),
                    end_ms=int(row[3]),
                    media_duration_ms=int(row[4]) if row[4] is not None else None,
                    member_count=int(row[5]),
                    source_count=int(row[6]),
                    lineage_count=int(row[7]),
                    confidence=float(row[8]),
                    algorithm=str(row[9]),
                    tolerance_ms=int(row[10]),
                )
                for row in conn.execute(query, tuple(params))
            ]

    def get_source_segments(
        self,
        source: str,
        source_episode_key: str,
        *,
        source_title_key: str = "",
    ) -> list[SourceSegment]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT ss.segment_type, ss.start_ms, ss.end_ms,
                       src.source_key, lin.lineage_key, ss.source_title_key,
                       ss.source_episode_key, ss.source_segment_id,
                       ss.media_duration_ms
                FROM source_segments ss
                JOIN sources src ON src.id=ss.source_id
                JOIN lineages lin ON lin.id=ss.lineage_id
                WHERE src.source_key=? AND ss.source_title_key=?
                  AND ss.source_episode_key=?
                ORDER BY ss.start_ms, ss.end_ms, ss.segment_type
                """,
                (
                    str(source).strip().casefold(),
                    str(source_title_key),
                    str(source_episode_key),
                ),
            )
            return [
                SourceSegment(
                    segment_type=str(row[0]),
                    start_ms=int(row[1]),
                    end_ms=int(row[2]),
                    source=str(row[3]),
                    lineage=str(row[4]),
                    source_title_key=str(row[5]),
                    source_episode_key=str(row[6]),
                    source_segment_id=str(row[7]),
                    media_duration_ms=int(row[8]) if row[8] is not None else None,
                )
                for row in rows
            ]
