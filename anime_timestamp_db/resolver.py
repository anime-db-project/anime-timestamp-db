from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from anime_timestamp_db.database import connect_readonly
from anime_timestamp_db.mapping_identity import (
    MappingAnchorIndex,
    format_anchor,
    parse_anchor,
)


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
    consensus_eligible: bool
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
class SourceTitleReference:
    source: str
    source_title_key: str
    identity_method: str


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
    """Read-only resolver for a published runtime timestamp database.

    Runtime identity is ``amdb:<anchor_id>``. A matching anime-mapping-db can be
    supplied for compatibility lookups from MAL/AniList/AniDB/etc. without
    copying those aliases into timestamps.db.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        mapping_path: Path | str | None = None,
    ) -> None:
        self.path = Path(path)
        self.mapping_path = Path(mapping_path) if mapping_path is not None else None

    def _connect(self) -> sqlite3.Connection:
        return connect_readonly(self.path)

    def anchor_for(self, provider: str, external_id: str) -> str | None:
        provider = str(provider).strip().casefold()
        external_id = str(external_id).strip()
        if provider == "amdb":
            try:
                return format_anchor(parse_anchor(external_id))
            except ValueError:
                return None
        if self.mapping_path is None:
            return None
        with MappingAnchorIndex(self.mapping_path) as mappings:
            anchor_id = mappings.anchor_for(provider, external_id)
        return format_anchor(anchor_id) if anchor_id is not None else None

    def title_ids(self, provider: str, external_id: str) -> dict[str, list[str]]:
        """Return external aliases from anime-mapping-db when it is attached."""

        reference = self.anchor_for(provider, external_id)
        if reference is None:
            return {}
        anchor_id = parse_anchor(reference)
        if self.mapping_path is None:
            return {"amdb": [str(anchor_id)]}
        with MappingAnchorIndex(self.mapping_path) as mappings:
            result = mappings.ids_for_anchor(anchor_id)
        result.setdefault("amdb", []).append(str(anchor_id))
        return result

    def _anchor_id(self, anchor: int | str) -> int | None:
        try:
            value = parse_anchor(anchor)
        except ValueError:
            return None
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT 1 FROM titles WHERE anchor_id=?", (value,)
            ).fetchone()
        return value if row is not None else None

    def episode_key_for_anchor(
        self,
        anchor: int | str,
        episode_number: int | float | str,
        *,
        provider: str | None = None,
        scope: str | None = None,
    ) -> str | None:
        anchor_id = self._anchor_id(anchor)
        if anchor_id is None:
            return None
        number_text = _episode_number_text(episode_number)
        with closing(self._connect()) as conn:
            if provider is None:
                rows = conn.execute(
                    """
                    SELECT episode_key FROM episodes
                    WHERE anchor_id=? AND episode_number_text=?
                    ORDER BY episode_key
                    """,
                    (anchor_id, number_text),
                ).fetchall()
            elif scope is None:
                rows = conn.execute(
                    """
                    SELECT DISTINCT ep.episode_key
                    FROM episode_ids eid
                    JOIN episodes ep ON ep.id=eid.episode_id
                    WHERE eid.anchor_id=? AND eid.provider=?
                      AND eid.episode_number_text=?
                    ORDER BY ep.episode_key
                    """,
                    (anchor_id, str(provider).strip().casefold(), number_text),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT ep.episode_key
                    FROM episode_ids eid
                    JOIN episodes ep ON ep.id=eid.episode_id
                    WHERE eid.anchor_id=? AND eid.provider=?
                      AND eid.scope=? AND eid.episode_number_text=?
                    ORDER BY ep.episode_key
                    """,
                    (
                        anchor_id,
                        str(provider).strip().casefold(),
                        str(scope).strip().upper(),
                        number_text,
                    ),
                ).fetchall()
        if len(rows) != 1:
            return None
        return str(rows[0][0])

    def episode_key(
        self,
        provider: str,
        external_id: str,
        episode_number: int | float | str,
        *,
        scope: str | None = None,
    ) -> str | None:
        """Compatibility resolver from an external title ID.

        For ``provider='amdb'`` no mapping database is needed. Other providers
        require ``mapping_path`` and use provider-specific episode numbering.
        """

        reference = self.anchor_for(provider, external_id)
        if reference is None:
            return None
        normalized_provider = str(provider).strip().casefold()
        return self.episode_key_for_anchor(
            reference,
            episode_number,
            provider=None if normalized_provider == "amdb" else normalized_provider,
            scope=scope,
        )

    def get_segments_by_anchor(
        self,
        anchor: int | str,
        episode_key: str,
        *,
        source: str | None = None,
        media_duration_ms: int | None = None,
    ) -> list[Segment]:
        anchor_id = self._anchor_id(anchor)
        if anchor_id is None:
            return []
        where_params: list[object] = [anchor_id, str(episode_key).strip()]
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
                   seg.consensus_eligible, seg.votes_up, seg.votes_down, {distance_select}
            FROM episodes ep
            JOIN segments seg ON seg.episode_id=ep.id
            JOIN sources src ON src.id=seg.source_id
            JOIN lineages lin ON lin.id=seg.lineage_id
            WHERE ep.anchor_id=? AND ep.episode_key=?
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
                    consensus_eligible=bool(row[10]),
                    votes_up=int(row[11]),
                    votes_down=int(row[12]),
                )
                for row in conn.execute(query, tuple(params))
            ]

    def get_segments(
        self,
        provider: str,
        external_id: str,
        episode_key: str,
        *,
        source: str | None = None,
        media_duration_ms: int | None = None,
    ) -> list[Segment]:
        reference = self.anchor_for(provider, external_id)
        if reference is None:
            return []
        return self.get_segments_by_anchor(
            reference,
            episode_key,
            source=source,
            media_duration_ms=media_duration_ms,
        )

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

    def get_consensus_by_anchor(
        self,
        anchor: int | str,
        episode_key: str,
        *,
        media_duration_ms: int | None = None,
    ) -> list[ConsensusSegment]:
        anchor_id = self._anchor_id(anchor)
        if anchor_id is None:
            return []
        if media_duration_ms is None:
            distance_select = "0 AS duration_distance"
            params: list[object] = [anchor_id, str(episode_key).strip()]
        else:
            distance_select = (
                "ABS(COALESCE(c.media_duration_ms, ?) - ?) AS duration_distance"
            )
            params = [
                media_duration_ms,
                media_duration_ms,
                anchor_id,
                str(episode_key).strip(),
            ]
        query = f"""
            SELECT c.segment_type, c.cluster_index, c.start_ms, c.end_ms,
                   c.media_duration_ms, c.member_count, c.source_count,
                   c.lineage_count, c.confidence, c.algorithm, c.tolerance_ms,
                   {distance_select}
            FROM episodes ep
            JOIN consensus_segments c ON c.episode_id=ep.id
            WHERE ep.anchor_id=? AND ep.episode_key=?
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

    def get_consensus(
        self,
        provider: str,
        external_id: str,
        episode_key: str,
        *,
        media_duration_ms: int | None = None,
    ) -> list[ConsensusSegment]:
        reference = self.anchor_for(provider, external_id)
        if reference is None:
            return []
        return self.get_consensus_by_anchor(
            reference,
            episode_key,
            media_duration_ms=media_duration_ms,
        )

    def get_source_title_refs_by_anchor(
        self, anchor: int | str
    ) -> list[SourceTitleReference]:
        """Show which native source title IDs have proven AMDB identity."""
        anchor_id = self._anchor_id(anchor)
        if anchor_id is None:
            return []
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT src.source_key, tr.source_title_key, tr.identity_method
                FROM source_title_refs AS tr
                JOIN sources AS src ON src.id=tr.source_id
                WHERE tr.anchor_id=?
                ORDER BY src.source_key, tr.source_title_key
                """,
                (anchor_id,),
            )
            return [
                SourceTitleReference(
                    source=str(row[0]),
                    source_title_key=str(row[1]),
                    identity_method=str(row[2]),
                )
                for row in rows
            ]

    def get_source_segments_by_anchor(
        self,
        anchor: int | str,
        *,
        source: str | None = None,
        source_episode_key: str | None = None,
    ) -> list[SourceSegment]:
        """Fetch source-native ranges without fabricating canonical episodes.

        This is intentionally separate from get_segments_by_anchor: even
        proven title identity does not prove a MAL/AniList episode identity.
        """
        anchor_id = self._anchor_id(anchor)
        if anchor_id is None:
            return []
        filters = ["tr.anchor_id=?"]
        params: list[object] = [anchor_id]
        if source is not None:
            filters.append("src.source_key=?")
            params.append(str(source).strip().casefold())
        if source_episode_key is not None:
            filters.append("ss.source_episode_key=?")
            params.append(str(source_episode_key))
        where = " AND ".join(filters)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""
                SELECT ss.segment_type, ss.start_ms, ss.end_ms,
                       src.source_key, lin.lineage_key, ss.source_title_key,
                       ss.source_episode_key, ss.source_segment_id,
                       ss.media_duration_ms
                FROM source_segments AS ss
                JOIN source_title_refs AS tr
                  ON tr.source_id=ss.source_id
                 AND tr.source_title_key=ss.source_title_key
                JOIN sources AS src ON src.id=ss.source_id
                JOIN lineages AS lin ON lin.id=ss.lineage_id
                WHERE {where}
                ORDER BY src.source_key, ss.source_title_key,
                         ss.source_episode_key, ss.start_ms,
                         ss.end_ms, ss.segment_type
                """,
                tuple(params),
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
