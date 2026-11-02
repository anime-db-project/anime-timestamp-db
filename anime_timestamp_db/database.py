from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from anime_timestamp_db.schema import EVIDENCE_SCHEMA, RUNTIME_SCHEMA, SCHEMA_VERSION


def _prepare_path(path: Path, *, overwrite: bool) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not overwrite:
            raise FileExistsError(path)
        path.unlink()
    return path


def _initialize_database(
    path: Path,
    *,
    role: str,
    schema: str,
    overwrite: bool,
) -> Path:
    path = _prepare_path(Path(path), overwrite=overwrite)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.executescript(schema)
        conn.executemany(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            (
                ("schema_version", str(SCHEMA_VERSION)),
                ("database_role", role),
                ("project", "anime-timestamp-db"),
            ),
        )
        conn.commit()
    return path


def create_runtime_database(path: Path, *, overwrite: bool = False) -> Path:
    return _initialize_database(
        Path(path),
        role="runtime",
        schema=RUNTIME_SCHEMA,
        overwrite=overwrite,
    )


def create_evidence_database(path: Path, *, overwrite: bool = False) -> Path:
    return _initialize_database(
        Path(path),
        role="evidence",
        schema=EVIDENCE_SCHEMA,
        overwrite=overwrite,
    )


def connect_readonly(path: Path) -> sqlite3.Connection:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    uri = f"{path.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _metadata(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row[0]): str(row[1])
        for row in conn.execute("SELECT key, value FROM metadata ORDER BY key")
    }


def inspect_database(path: Path) -> dict[str, Any]:
    with closing(connect_readonly(path)) as conn:
        metadata = _metadata(conn)
        role = metadata.get("database_role", "")
        schema_version = metadata.get("schema_version", "")
        if schema_version != str(SCHEMA_VERSION):
            raise ValueError(
                f"Unsupported schema version {schema_version!r}; "
                f"expected {SCHEMA_VERSION}"
            )

        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        counts: dict[str, int] = {}
        if role == "runtime":
            wanted = (
                "sources",
                "lineages",
                "titles",
                "title_ids",
                "episodes",
                "episode_refs",
                "segments",
                "consensus_segments",
                "consensus_members",
            )
        elif role == "evidence":
            wanted = ("source_snapshots", "records", "record_segments")
        else:
            raise ValueError(f"Unknown database role {role!r}")

        for table in wanted:
            if table not in tables:
                raise ValueError(f"Missing required table {table!r}")
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0]) if row is not None else 0

        return {
            "path": str(Path(path)),
            "metadata": metadata,
            "counts": counts,
        }


def inspect_database_json(path: Path) -> str:
    return json.dumps(
        inspect_database(path),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
