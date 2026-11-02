from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Iterable


def create_mapping_db(
    path: Path,
    *,
    nodes: Iterable[tuple[int, str, str]],
    edges: Iterable[tuple[int, int]] = (),
    anchors: dict[int, Iterable[int]] | None = None,
    conflicts: Iterable[tuple[int, str, list[str], str]] = (),
) -> None:
    nodes = list(nodes)
    edges = list(edges)
    conflicts = list(conflicts)
    normalized_anchors = {
        int(anchor_id): [int(node_id) for node_id in node_ids]
        for anchor_id, node_ids in (anchors or {}).items()
    }
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE nodes (
                id INTEGER PRIMARY KEY,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                UNIQUE(provider, external_id)
            );
            CREATE TABLE edges (
                a_node INTEGER NOT NULL,
                b_node INTEGER NOT NULL,
                confidence INTEGER NOT NULL,
                status TEXT NOT NULL,
                evidence_count INTEGER NOT NULL,
                evidence_group_count INTEGER NOT NULL,
                max_weight INTEGER NOT NULL,
                PRIMARY KEY(a_node, b_node)
            ) WITHOUT ROWID;
            CREATE TABLE conflicts (
                source_node INTEGER NOT NULL,
                target_provider TEXT NOT NULL,
                candidate_ids_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                PRIMARY KEY(source_node, target_provider)
            ) WITHOUT ROWID;
            CREATE TABLE entities (
                entity_id INTEGER PRIMARY KEY,
                anchor_id INTEGER NOT NULL UNIQUE
            );
            CREATE TABLE entity_nodes (
                entity_id INTEGER NOT NULL,
                node_id INTEGER NOT NULL,
                PRIMARY KEY(entity_id, node_id),
                UNIQUE(node_id)
            ) WITHOUT ROWID;
            CREATE TABLE anchor_redirects (
                old_anchor_id INTEGER PRIMARY KEY,
                anchor_id INTEGER NOT NULL,
                reason TEXT NOT NULL DEFAULT 'merged'
            ) WITHOUT ROWID;
            """
        )
        conn.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (
                ("schema_version", "3"),
                ("database_role", "runtime"),
                ("built_at", "2026-11-02T00:00:00+00:00"),
                ("anchor_schema_version", "1"),
                ("anchor_namespace", "amdb"),
                ("anchor_format", "amdb:<integer>"),
                ("anchor_entities", str(len(normalized_anchors))),
                (
                    "anchor_nodes",
                    str(sum(len(node_ids) for node_ids in normalized_anchors.values())),
                ),
            ),
        )
        conn.executemany(
            "INSERT INTO nodes(id, provider, external_id) VALUES (?, ?, ?)",
            nodes,
        )
        for left, right in edges:
            conn.execute(
                """
                INSERT INTO edges(
                    a_node, b_node, confidence, status,
                    evidence_count, evidence_group_count, max_weight
                ) VALUES (?, ?, 100, 'accepted', 1, 1, 100)
                """,
                (min(left, right), max(left, right)),
            )
        for source, provider, candidate_ids, reason in conflicts:
            conn.execute(
                """
                INSERT INTO conflicts(
                    source_node, target_provider, candidate_ids_json, reason
                ) VALUES (?, ?, ?, ?)
                """,
                (source, provider, json.dumps(candidate_ids), reason),
            )
        for entity_id, (anchor_id, node_ids) in enumerate(
            sorted(normalized_anchors.items()), start=1
        ):
            conn.execute(
                "INSERT INTO entities(entity_id, anchor_id) VALUES (?, ?)",
                (entity_id, anchor_id),
            )
            conn.executemany(
                "INSERT INTO entity_nodes(entity_id, node_id) VALUES (?, ?)",
                ((entity_id, node_id) for node_id in node_ids),
            )
        conn.commit()
