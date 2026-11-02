from __future__ import annotations

import argparse
from pathlib import Path

from anime_timestamp_db.database import (
    create_evidence_database,
    create_runtime_database,
    inspect_database_json,
)
from anime_timestamp_db.schema import (
    DEFAULT_EVIDENCE_DB_NAME,
    DEFAULT_RUNTIME_DB_NAME,
    SCHEMA_VERSION,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anime-timestamp-db")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", help="Create empty runtime and evidence databases"
    )
    init_parser.add_argument("--db", type=Path, default=Path(DEFAULT_RUNTIME_DB_NAME))
    init_parser.add_argument(
        "--evidence-db",
        type=Path,
        default=Path(DEFAULT_EVIDENCE_DB_NAME),
    )
    init_parser.add_argument(
        "--force", action="store_true", help="Replace existing database files"
    )

    inspect_parser = subparsers.add_parser(
        "inspect", help="Print schema metadata and table counts as JSON"
    )
    inspect_parser.add_argument("--db", type=Path, required=True)

    subparsers.add_parser("schema-version", help="Print the supported schema version")
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
    if args.command == "schema-version":
        print(SCHEMA_VERSION)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
