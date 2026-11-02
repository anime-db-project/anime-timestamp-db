from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from anime_timestamp_db.database import connect_readonly


@dataclass(frozen=True, slots=True)
class Segment:
    segment_type: str
    start_ms: int
    end_ms: int
    source: str
    lineage: str
    source_segment_id: str
    confidence: float | None
    is_derived: bool


@dataclass(frozen=True, slots=True)
class ConsensusSegment:
    segment_type: str
    cluster_index: int
    start_ms: int
    end_ms: int
    member_count: int
    lineage_count: int
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
            title_id = int(row[0])
            result: dict[str, list[str]] = {}
            for item in conn.execute(
                """
                SELECT provider, external_id
                FROM title_ids
                WHERE title_id=?
                ORDER BY provider, external_id
                """,
                (title_id,),
            ):
                result.setdefault(str(item[0]), []).append(str(item[1]))
            return result

    def get_segments(
        self,
        provider: str,
        external_id: str,
        episode_key: str,
        *,
        source: str | None = None,
    ) -> list[Segment]:
        params: list[object] = [
            str(provider).strip().casefold(),
            str(external_id).strip(),
            str(episode_key).strip(),
        ]
        source_sql = ""
        if source is not None:
            source_sql = " AND src.source_key=?"
            params.append(str(source).strip().casefold())

        query = f"""
            SELECT
                seg.segment_type,
                seg.start_ms,
                seg.end_ms,
                src.source_key,
                lin.lineage_key,
                seg.source_segment_id,
                seg.confidence,
                seg.is_derived
            FROM title_ids AS tid
            JOIN episodes AS ep ON ep.title_id = tid.title_id
            JOIN segments AS seg ON seg.episode_id = ep.id
            JOIN sources AS src ON src.id = seg.source_id
            JOIN lineages AS lin ON lin.id = seg.lineage_id
            WHERE tid.provider=?
              AND tid.external_id=?
              AND ep.episode_key=?
              {source_sql}
            ORDER BY seg.start_ms, seg.end_ms, seg.segment_type, src.source_key
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
                    confidence=float(row[6]) if row[6] is not None else None,
                    is_derived=bool(row[7]),
                )
                for row in conn.execute(query, tuple(params))
            ]

    def get_consensus(
        self,
        provider: str,
        external_id: str,
        episode_key: str,
    ) -> list[ConsensusSegment]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT
                    c.segment_type,
                    c.cluster_index,
                    c.start_ms,
                    c.end_ms,
                    c.member_count,
                    c.lineage_count,
                    c.algorithm,
                    c.tolerance_ms
                FROM title_ids AS tid
                JOIN episodes AS ep ON ep.title_id = tid.title_id
                JOIN consensus_segments AS c ON c.episode_id = ep.id
                WHERE tid.provider=?
                  AND tid.external_id=?
                  AND ep.episode_key=?
                ORDER BY c.start_ms, c.end_ms, c.segment_type, c.cluster_index
                """,
                (
                    str(provider).strip().casefold(),
                    str(external_id).strip(),
                    str(episode_key).strip(),
                ),
            )
            return [
                ConsensusSegment(
                    segment_type=str(row[0]),
                    cluster_index=int(row[1]),
                    start_ms=int(row[2]),
                    end_ms=int(row[3]),
                    member_count=int(row[4]),
                    lineage_count=int(row[5]),
                    algorithm=str(row[6]),
                    tolerance_ms=int(row[7]),
                )
                for row in rows
            ]
