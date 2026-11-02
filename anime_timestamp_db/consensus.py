from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True, slots=True)
class _Observation:
    segment_id: int
    source_id: int
    lineage_id: int
    start_ms: int
    end_ms: int
    media_duration_ms: int | None
    quality_score: float | None
    mapping_confidence: float
    votes_up: int


@dataclass(slots=True)
class _Cluster:
    observations: list[_Observation]

    @property
    def representatives(self) -> list[_Observation]:
        """Choose one vote per provenance lineage inside a timing cluster."""
        best: dict[int, _Observation] = {}
        for item in self.observations:
            current = best.get(item.lineage_id)
            rank = (
                item.mapping_confidence,
                float(item.quality_score or 0.0),
                item.votes_up,
                -item.source_id,
                -item.segment_id,
            )
            if current is None:
                best[item.lineage_id] = item
                continue
            current_rank = (
                current.mapping_confidence,
                float(current.quality_score or 0.0),
                current.votes_up,
                -current.source_id,
                -current.segment_id,
            )
            if rank > current_rank:
                best[item.lineage_id] = item
        return [best[key] for key in sorted(best)]

    @property
    def center(self) -> tuple[int, int, int | None]:
        representatives = self.representatives
        starts = [item.start_ms for item in representatives]
        ends = [item.end_ms for item in representatives]
        durations = [
            item.media_duration_ms
            for item in representatives
            if item.media_duration_ms is not None
        ]
        return (
            round(median(starts)),
            round(median(ends)),
            round(median(durations)) if durations else None,
        )


def _iou(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    overlap = max(0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    return 0.0 if union <= 0 else overlap / union


def _compatible(
    observation: _Observation,
    cluster: _Cluster,
    *,
    tolerance_ms: int,
    duration_tolerance_ms: int,
) -> bool:
    center_start, center_end, center_duration = cluster.center
    if (
        observation.media_duration_ms is not None
        and center_duration is not None
        and abs(observation.media_duration_ms - center_duration) > duration_tolerance_ms
    ):
        return False
    close_boundaries = (
        abs(observation.start_ms - center_start) <= tolerance_ms
        and abs(observation.end_ms - center_end) <= tolerance_ms
    )
    return (
        close_boundaries
        or _iou(
            observation.start_ms,
            observation.end_ms,
            center_start,
            center_end,
        )
        >= 0.75
    )


def _weight(item: _Observation) -> float:
    score = max(0.0, float(item.quality_score or 0.0))
    base = 1.0 + score + 0.25 * math.log1p(max(0, item.votes_up))
    return base * max(0.05, min(1.0, item.mapping_confidence))


def _weighted_median(items: list[tuple[int, float]]) -> int:
    ordered = sorted(items, key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    cursor = 0.0
    for value, weight in ordered:
        cursor += weight
        if cursor >= total / 2:
            return int(value)
    return int(ordered[-1][0])


def _confidence(cluster: _Cluster, *, tolerance_ms: int) -> float:
    center_start, center_end, _ = cluster.center
    representatives = cluster.representatives
    dispersion = sum(
        abs(item.start_ms - center_start) + abs(item.end_ms - center_end)
        for item in representatives
    ) / max(1, len(representatives) * 2)
    agreement = 1.0 / (1.0 + dispersion / max(1, tolerance_ms))
    lineages = len(representatives)
    support = min(1.0, 0.45 + 0.15 * math.sqrt(lineages) + 0.15 * (lineages - 1))
    return round(max(0.0, min(1.0, agreement * support)), 6)


def rebuild_consensus(
    conn: sqlite3.Connection,
    *,
    tolerance_ms: int = 5000,
    duration_tolerance_ms: int = 10000,
) -> dict[str, int]:
    """Materialize deterministic consensus clusters from normalized observations."""

    conn.execute("DELETE FROM consensus_members")
    conn.execute("DELETE FROM consensus_segments")

    groups = conn.execute(
        """
        SELECT DISTINCT episode_id, segment_type
        FROM segments
        ORDER BY episode_id, segment_type
        """
    ).fetchall()
    consensus_count = 0
    member_count = 0

    for episode_id, segment_type in groups:
        rows = conn.execute(
            """
            SELECT id, source_id, lineage_id, start_ms, end_ms,
                   media_duration_ms, quality_score, mapping_confidence, votes_up
            FROM segments
            WHERE episode_id=? AND segment_type=? AND consensus_eligible=1
            ORDER BY start_ms, end_ms, id
            """,
            (episode_id, segment_type),
        ).fetchall()
        observations = [
            _Observation(
                segment_id=int(row[0]),
                source_id=int(row[1]),
                lineage_id=int(row[2]),
                start_ms=int(row[3]),
                end_ms=int(row[4]),
                media_duration_ms=int(row[5]) if row[5] is not None else None,
                quality_score=float(row[6]) if row[6] is not None else None,
                mapping_confidence=float(row[7]),
                votes_up=int(row[8]),
            )
            for row in rows
        ]

        clusters: list[_Cluster] = []
        for observation in observations:
            candidates = [
                cluster
                for cluster in clusters
                if _compatible(
                    observation,
                    cluster,
                    tolerance_ms=tolerance_ms,
                    duration_tolerance_ms=duration_tolerance_ms,
                )
            ]
            if not candidates:
                clusters.append(_Cluster([observation]))
                continue
            chosen = min(
                candidates,
                key=lambda cluster: (
                    abs(observation.start_ms - cluster.center[0])
                    + abs(observation.end_ms - cluster.center[1]),
                    cluster.center[0],
                    cluster.center[1],
                ),
            )
            chosen.observations.append(observation)

        clusters.sort(key=lambda cluster: (cluster.center[0], cluster.center[1]))
        for cluster_index, cluster in enumerate(clusters):
            representatives = cluster.representatives
            weighted = [(item, _weight(item)) for item in representatives]
            start_ms = _weighted_median(
                [(item.start_ms, weight) for item, weight in weighted]
            )
            end_ms = _weighted_median(
                [(item.end_ms, weight) for item, weight in weighted]
            )
            durations = [
                (item.media_duration_ms, weight)
                for item, weight in weighted
                if item.media_duration_ms is not None
            ]
            media_duration_ms = _weighted_median(durations) if durations else None
            if end_ms <= start_ms:
                continue
            source_count = len({item.source_id for item in cluster.observations})
            lineage_count = len({item.lineage_id for item in cluster.observations})
            cursor = conn.execute(
                """
                INSERT INTO consensus_segments(
                    episode_id, segment_type, cluster_index, start_ms, end_ms,
                    media_duration_ms, member_count, source_count, lineage_count,
                    confidence, algorithm, tolerance_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'weighted-median-v1', ?)
                """,
                (
                    episode_id,
                    segment_type,
                    cluster_index,
                    start_ms,
                    end_ms,
                    media_duration_ms,
                    len(cluster.observations),
                    source_count,
                    lineage_count,
                    _confidence(cluster, tolerance_ms=tolerance_ms),
                    tolerance_ms,
                ),
            )
            assert cursor.lastrowid is not None
            consensus_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT INTO consensus_members(consensus_id, segment_id) VALUES (?, ?)",
                ((consensus_id, item.segment_id) for item in cluster.observations),
            )
            consensus_count += 1
            member_count += len(cluster.observations)

    conn.commit()
    return {"consensus_segments": consensus_count, "consensus_members": member_count}
