from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from anime_timestamp_db.database import connect_readonly, count_by
from anime_timestamp_db.schema import SCHEMA_VERSION


def _scalar(conn: sqlite3.Connection, query: str) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0]) if row is not None else 0


def audit_runtime(path: Path) -> dict[str, Any]:
    with closing(connect_readonly(path)) as conn:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        invalid_segments = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM segments
            WHERE start_ms < 0 OR end_ms <= start_ms
               OR (media_duration_ms IS NOT NULL AND media_duration_ms <= 0)
            """,
        )
        invalid_source_segments = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM source_segments
            WHERE start_ms < 0 OR end_ms <= start_ms
               OR (media_duration_ms IS NOT NULL AND media_duration_ms <= 0)
            """,
        )
        bad_consensus_members = _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM consensus_segments AS c
            LEFT JOIN (
                SELECT consensus_id, COUNT(*) AS n
                FROM consensus_members
                GROUP BY consensus_id
            ) AS m ON m.consensus_id = c.id
            WHERE COALESCE(m.n, 0) <> c.member_count
            """,
        )
        orphan_episodes = _scalar(
            conn,
            """
            SELECT COUNT(*) FROM episodes AS e
            WHERE NOT EXISTS (SELECT 1 FROM segments s WHERE s.episode_id=e.id)
            """,
        )
        provider_episode_identity_errors = _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM episode_ids AS eid
            JOIN episodes AS ep ON ep.id=eid.episode_id
            WHERE NOT EXISTS (
                SELECT 1 FROM title_ids AS tid
                WHERE tid.title_id=ep.title_id
                  AND tid.provider=eid.provider
                  AND tid.external_id=eid.title_external_id
            )
            """,
        )
        counts = {
            table: _scalar(conn, f"SELECT COUNT(*) FROM {table}")
            for table in (
                "sources",
                "lineages",
                "titles",
                "title_ids",
                "episodes",
                "episode_ids",
                "episode_refs",
                "segments",
                "source_segments",
                "consensus_segments",
                "consensus_members",
            )
        }
        report = {
            "schema_version": user_version,
            "integrity_check": integrity,
            "foreign_key_errors": len(foreign_keys),
            "invalid_segments": invalid_segments,
            "invalid_source_segments": invalid_source_segments,
            "consensus_member_mismatches": bad_consensus_members,
            "orphan_episodes": orphan_episodes,
            "provider_episode_identity_errors": provider_episode_identity_errors,
            "counts": counts,
            "segments_by_source": count_by(
                conn,
                """
                SELECT src.source_key, COUNT(*)
                FROM segments s JOIN sources src ON src.id=s.source_id
                GROUP BY src.source_key ORDER BY src.source_key
                """,
            ),
            "source_segments_by_source": count_by(
                conn,
                """
                SELECT src.source_key, COUNT(*)
                FROM source_segments s JOIN sources src ON src.id=s.source_id
                GROUP BY src.source_key ORDER BY src.source_key
                """,
            ),
            "segments_by_type": count_by(
                conn,
                "SELECT segment_type, COUNT(*) FROM segments GROUP BY segment_type ORDER BY segment_type",
            ),
            "source_segments_by_type": count_by(
                conn,
                "SELECT segment_type, COUNT(*) FROM source_segments GROUP BY segment_type ORDER BY segment_type",
            ),
        }
        report["ok"] = bool(
            integrity == "ok"
            and user_version == SCHEMA_VERSION
            and not foreign_keys
            and invalid_segments == 0
            and invalid_source_segments == 0
            and bad_consensus_members == 0
            and orphan_episodes == 0
            and provider_episode_identity_errors == 0
            and counts["segments"] > 0
            and counts["source_segments"] > 0
        )
        return report


def audit_evidence(path: Path) -> dict[str, Any]:
    with closing(connect_readonly(path)) as conn:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        counts = {
            table: _scalar(conn, f"SELECT COUNT(*) FROM {table}")
            for table in ("source_snapshots", "records", "record_segments")
        }
        report = {
            "schema_version": user_version,
            "integrity_check": integrity,
            "foreign_key_errors": len(foreign_keys),
            "counts": counts,
            "normalization_statuses": count_by(
                conn,
                """
                SELECT normalization_status, COUNT(*) FROM records
                GROUP BY normalization_status ORDER BY normalization_status
                """,
            ),
            "records_by_source": count_by(
                conn,
                """
                SELECT s.source_key, COUNT(r.id)
                FROM source_snapshots s LEFT JOIN records r ON r.snapshot_id=s.id
                GROUP BY s.source_key ORDER BY s.source_key
                """,
            ),
        }
        report["ok"] = bool(
            integrity == "ok"
            and user_version == SCHEMA_VERSION
            and not foreign_keys
            and counts["records"] > 0
            and counts["record_segments"] > 0
        )
        return report


def audit_databases(runtime_path: Path, evidence_path: Path) -> dict[str, Any]:
    runtime = audit_runtime(runtime_path)
    evidence = audit_evidence(evidence_path)
    return {
        "ok": bool(runtime["ok"] and evidence["ok"]),
        "runtime": runtime,
        "evidence": evidence,
    }


def audit_json(runtime_path: Path, evidence_path: Path) -> str:
    return json.dumps(
        audit_databases(runtime_path, evidence_path),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
