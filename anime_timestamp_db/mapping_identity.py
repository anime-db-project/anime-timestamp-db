from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

import zstandard as zstd

ANCHOR_NAMESPACE = "amdb"
SUPPORTED_ANCHOR_SCHEMA_VERSION = "1"


class AnchorResolutionConflict(RuntimeError):
    """Raised when provider IDs unexpectedly resolve to different AMDB anchors."""


@dataclass(slots=True)
class AnchorLookupStats:
    lookups: int = 0
    cache_hits: int = 0
    resolved: int = 0
    missing: int = 0
    conflicts: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def format_anchor(anchor_id: int) -> str:
    value = int(anchor_id)
    if value <= 0:
        raise ValueError("anchor_id must be positive")
    return f"{ANCHOR_NAMESPACE}:{value}"


def parse_anchor(value: int | str) -> int:
    if isinstance(value, int):
        anchor_id = value
    else:
        text = str(value).strip().casefold()
        prefix = f"{ANCHOR_NAMESPACE}:"
        if text.startswith(prefix):
            text = text[len(prefix) :]
        if not text.isdigit():
            raise ValueError(f"invalid anchor reference: {value!r}")
        anchor_id = int(text)
    if anchor_id <= 0:
        raise ValueError("anchor_id must be positive")
    return anchor_id


def _connect_readonly(path: Path) -> sqlite3.Connection:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    conn = sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def decompress_mapping_database(source: Path, target: Path) -> Path:
    """Decompress a hash-addressed ``mappings.db.zst`` and validate SQLite."""

    source = Path(source)
    target = Path(target)
    if target.is_file():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.unlink(missing_ok=True)

    decompressor = zstd.ZstdDecompressor()
    try:
        with source.open("rb") as src, temporary.open("wb") as dst:
            decompressor.copy_stream(src, dst)
        with closing(_connect_readonly(temporary)) as conn:
            quick_check = conn.execute("PRAGMA quick_check").fetchone()
            if quick_check is None or str(quick_check[0]) != "ok":
                raise RuntimeError(
                    f"anime-mapping-db quick_check failed: {quick_check!r}"
                )
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)

    return target


def mapping_database_metadata(path: Path) -> dict[str, str]:
    with closing(_connect_readonly(path)) as conn:
        tables = {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required = {
            "metadata",
            "nodes",
            "entities",
            "entity_nodes",
            "anchor_redirects",
        }
        missing = sorted(required - tables)
        if missing:
            raise ValueError(
                "anime-mapping-db is missing required identity tables: "
                + ", ".join(missing)
            )
        metadata = {
            str(row[0]): str(row[1])
            for row in conn.execute("SELECT key, value FROM metadata ORDER BY key")
        }
        if metadata.get("database_role") != "runtime":
            raise ValueError("anime-mapping-db input is not a runtime mapping database")
        anchor_schema = metadata.get("anchor_schema_version", "")
        if anchor_schema != SUPPORTED_ANCHOR_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported anime-mapping-db anchor schema "
                f"{anchor_schema!r}; expected {SUPPORTED_ANCHOR_SCHEMA_VERSION}"
            )
        if metadata.get("anchor_namespace") != ANCHOR_NAMESPACE:
            raise ValueError(
                "anime-mapping-db anchor namespace is not the expected 'amdb'"
            )
        return metadata


class MappingAnchorIndex:
    """Read-only bridge from provider IDs to stable ``amdb:<anchor_id>`` IDs.

    The timestamp database deliberately does not copy title aliases from
    anime-mapping-db. During a build this index resolves the source-native IDs
    once and the runtime database persists only the stable numeric anchor.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path).resolve()
        self.metadata = mapping_database_metadata(self.path)
        self.conn = _connect_readonly(self.path)
        self._cache: dict[tuple[str, str], int | None] = {}
        self.stats = AnchorLookupStats()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "MappingAnchorIndex":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def anchor_for(self, provider: str, external_id: str) -> int | None:
        key = (str(provider).strip().casefold(), str(external_id).strip())
        if not key[0] or not key[1]:
            return None
        self.stats.lookups += 1
        if key in self._cache:
            self.stats.cache_hits += 1
            return self._cache[key]
        row = self.conn.execute(
            """
            SELECT e.anchor_id
            FROM nodes AS n
            JOIN entity_nodes AS en ON en.node_id=n.id
            JOIN entities AS e ON e.entity_id=en.entity_id
            WHERE n.provider=? AND n.external_id=?
            """,
            key,
        ).fetchone()
        anchor_id = int(row[0]) if row is not None else None
        self._cache[key] = anchor_id
        if anchor_id is None:
            self.stats.missing += 1
        else:
            self.stats.resolved += 1
        return anchor_id

    def anchor_for_ids(self, ids: Mapping[str, str]) -> int | None:
        resolved = {
            anchor_id
            for provider, external_id in ids.items()
            if (anchor_id := self.anchor_for(provider, external_id)) is not None
        }
        if len(resolved) > 1:
            self.stats.conflicts += 1
            normalized = {
                str(provider).strip().casefold(): str(external_id).strip()
                for provider, external_id in ids.items()
                if str(provider).strip() and str(external_id).strip()
            }
            raise AnchorResolutionConflict(
                f"provider IDs resolve to multiple AMDB anchors: {normalized}"
            )
        return next(iter(resolved)) if resolved else None

    def ids_for_anchor(self, anchor_id: int | str) -> dict[str, list[str]]:
        anchor = parse_anchor(anchor_id)
        rows = self.conn.execute(
            """
            SELECT n.provider, n.external_id
            FROM entities AS e
            JOIN entity_nodes AS en ON en.entity_id=e.entity_id
            JOIN nodes AS n ON n.id=en.node_id
            WHERE e.anchor_id=?
            ORDER BY n.provider, n.external_id
            """,
            (anchor,),
        )
        result: dict[str, list[str]] = {}
        for provider, external_id in rows:
            result.setdefault(str(provider), []).append(str(external_id))
        return result
