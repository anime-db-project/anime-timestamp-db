from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from anime_timestamp_db.audit import audit_databases
from anime_timestamp_db.database import (
    create_evidence_database,
    create_runtime_database,
    inspect_database_json,
)
from anime_timestamp_db.pipeline import build_database
from anime_timestamp_db.resolver import TimestampResolver
from anime_timestamp_db.schema import (
    DEFAULT_EVIDENCE_DB_NAME,
    DEFAULT_RUNTIME_DB_NAME,
    SCHEMA_VERSION,
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anime-timestamp-db")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create empty schema databases")
    init_parser.add_argument("--db", type=Path, default=Path(DEFAULT_RUNTIME_DB_NAME))
    init_parser.add_argument(
        "--evidence-db", type=Path, default=Path(DEFAULT_EVIDENCE_DB_NAME)
    )
    init_parser.add_argument("--force", action="store_true")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one database")
    inspect_parser.add_argument("--db", type=Path, required=True)

    build_cmd = subparsers.add_parser(
        "build", help="Download public bulk datasets and build artifact databases"
    )
    build_cmd.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    build_cmd.add_argument("--cache-dir", type=Path)
    build_cmd.add_argument("--force-download", action="store_true")
    build_cmd.add_argument("--consensus-tolerance-ms", type=int, default=5000)

    audit_cmd = subparsers.add_parser(
        "audit", help="Audit runtime + evidence databases"
    )
    audit_cmd.add_argument("--db", type=Path, required=True)
    audit_cmd.add_argument("--evidence-db", type=Path, required=True)

    lookup = subparsers.add_parser("lookup", help="Resolve normalized anime timestamps")
    lookup.add_argument("--db", type=Path, required=True)
    lookup.add_argument(
        "--mapping-db",
        type=Path,
        help=(
            "Optional anime-mapping-db mappings.db for MAL/AniList/AniDB/etc. "
            "lookups. Not required when --provider amdb is used."
        ),
    )
    lookup.add_argument("--provider", required=True)
    lookup.add_argument("--id", required=True)
    episode_group = lookup.add_mutually_exclusive_group(required=True)
    episode_group.add_argument("--episode-key")
    episode_group.add_argument("--episode")
    lookup.add_argument("--source")
    lookup.add_argument("--scope")
    lookup.add_argument("--duration-ms", type=int)
    lookup.add_argument("--consensus", action="store_true")

    source_lookup = subparsers.add_parser(
        "source-lookup",
        help="Resolve source-addressable timestamps such as Baha videoSn",
    )
    source_lookup.add_argument("--db", type=Path, required=True)
    source_lookup.add_argument("--source", required=True)
    source_lookup.add_argument("--episode-key", required=True)
    source_lookup.add_argument("--title-key", default="")

    subparsers.add_parser("schema-version", help="Print schema version")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        create_runtime_database(args.db, overwrite=args.force)
        create_evidence_database(args.evidence_db, overwrite=args.force)
        print(args.db)
        print(args.evidence_db)
        return 0
    if args.command == "inspect":
        print(inspect_database_json(args.db))
        return 0
    if args.command == "build":
        manifest = build_database(
            args.output_dir,
            cache_dir=args.cache_dir,
            force_download=args.force_download,
            consensus_tolerance_ms=args.consensus_tolerance_ms,
        )
        print(_json(manifest))
        return 0
    if args.command == "audit":
        report = audit_databases(args.db, args.evidence_db)
        print(_json(report))
        return 0 if report["ok"] else 1
    if args.command == "lookup":
        resolver = TimestampResolver(args.db, mapping_path=args.mapping_db)
        key = args.episode_key
        if key is None:
            key = resolver.episode_key(
                args.provider, args.id, args.episode, scope=args.scope
            )
        if key is None:
            print("[]")
            return 0
        if args.consensus:
            rows = resolver.get_consensus(
                args.provider,
                args.id,
                key,
                media_duration_ms=args.duration_ms,
            )
        else:
            rows = resolver.get_segments(
                args.provider,
                args.id,
                key,
                source=args.source,
                media_duration_ms=args.duration_ms,
            )
        print(_json([asdict(row) for row in rows]))
        return 0
    if args.command == "source-lookup":
        resolver = TimestampResolver(args.db)
        rows = resolver.get_source_segments(
            args.source,
            args.episode_key,
            source_title_key=args.title_key,
        )
        print(_json([asdict(row) for row in rows]))
        return 0
    if args.command == "schema-version":
        print(SCHEMA_VERSION)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
