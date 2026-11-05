"""Incremental, permission-gated third-party skip sources.

Output is source-native provenance, not guessed MAL episode equivalence.
Published cross-source SQLite ingestion is a separate licensed opt-in.
"""

from __future__ import annotations

import gzip
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx

from scripts.external_sources import (
    PREFERRED_PROVIDER,
    make_request,
    parse_segments,
)
from scripts.source_policies import PacedLimiter, load_policies


def external_candidates(
    source: str,
    catalog: dict[int, dict[str, str]],
    state: dict[str, Any],
    *,
    max_episodes: int,
    unknown_episodes: int,
) -> list[tuple[str, int, str, str, int, int]]:
    """Start with a small season-one frontier; advance only on positives."""
    result = []
    for anchor, ids in sorted(catalog.items()):
        identity = next(
            (
                (provider, ids[provider])
                for provider in PREFERRED_PROVIDER[source]
                if ids.get(provider)
            ),
            None,
        )
        if not identity:
            continue
        provider, native = identity
        seen_positive: set[int] = set()
        prefix = f"{provider}:{native}:1:"
        for key, record in state["records"].items():
            if (
                key.startswith(prefix)
                and isinstance(record, dict)
                and (record.get("status") == "found")
            ):
                token = key.rsplit(":", 1)[-1]
                if token.isdigit():
                    seen_positive.add(int(token))
        upto = min(
            max_episodes, max([unknown_episodes, *(n + 2 for n in seen_positive)])
        )
        for episode in range(1, upto + 1):
            key = f"{prefix}{episode}"
            result.append((key, anchor, provider, native, 1, episode))
    return result


def export_external(
    source: str,
    state: dict[str, Any],
    catalog: dict[int, dict[str, str]],
    path: Path,
) -> dict[str, int]:
    from scripts.crawl_timestamps import write_gzip_json

    owners: dict[tuple[str, str], int] = {}
    for anchor, ids in catalog.items():
        for provider in PREFERRED_PROVIDER[source]:
            if provider in ids:
                owners[(provider, ids[provider])] = anchor
    rows: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for key, record in sorted(state["records"].items()):
        if not isinstance(record, dict) or record.get("status") != "found":
            continue
        for segment in record.get("segments", []):
            if not isinstance(segment, dict) or segment.get("source") != source:
                continue
            provider = str(segment.get("native_provider") or "")
            native = str(segment.get("native_title_id") or "")
            season, episode = segment.get("season"), segment.get("episode")
            if key != f"{provider}:{native}:{season}:{episode}":
                continue
            anchor = owners.get((provider, native))
            if anchor is None:
                continue
            row = dict(segment)
            row["anchor_id"] = anchor
            rows.append(row)
            identities.add((provider, native))
    rows.sort(
        key=lambda v: (
            v["anchor_id"],
            v["native_provider"],
            v["season"],
            v["episode"],
            v["type"],
            v["start_ms"],
            v["source_segment_id"],
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    try:
        with gzip.open(part, "wt", encoding="utf-8") as out:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        part.replace(path)
    finally:
        part.unlink(missing_ok=True)
    return {"observations": len(rows), "titles": len(identities)}


async def crawl_external(args, *, client: httpx.AsyncClient | None = None):
    from scripts.crawl_timestamps import (
        BadUpstreamResponse,
        BudgetExhausted,
        RateLimited,
        due,
        file_sha256,
        load_catalog,
        load_state,
        now,
        request_json,
        utc_string,
        write_gzip_json,
    )

    source = args.source
    policy = load_policies()[source]
    if getattr(args, "rpm", None) is not None:
        policy = replace(policy, per_minute=min(args.rpm, policy.per_minute))
    if (
        policy.requires_bulk_permission
        and os.getenv("BULK_SOURCE_PERMISSION_" + source.upper(), "").strip().lower()
        != "true"
        and not (args.dry_run or args.export_only)
    ):
        raise ValueError(f"{source}: explicit permission required for bulk crawling")
    api_key = getattr(args, "publicmetadb_api_key", "") or ""
    if (
        source == "publicmetadb"
        and not api_key
        and not (args.dry_run or args.export_only)
    ):
        raise ValueError("PUBLICMETADB_API_KEY required")

    providers = PREFERRED_PROVIDER[source]
    catalog, catalog_stats = load_catalog(args.mapping_db, providers)
    only_anchor = getattr(args, "only_anchor", None)
    if only_anchor is not None:
        if only_anchor not in catalog:
            raise ValueError("unknown AMDB anchor")
        catalog = {only_anchor: catalog[only_anchor]}
    state_path = args.state_dir / f"{source}.json.gz"
    state = load_state(state_path, source)
    records: dict[str, Any] = state["records"]
    candidates = external_candidates(
        source,
        catalog,
        state,
        max_episodes=args.max_episodes,
        unknown_episodes=args.unknown_episodes,
    )
    pending = [
        item
        for item in candidates
        if due(
            records.get(item[0]),
            positive_days=args.positive_ttl_days,
            negative_days=args.negative_ttl_days,
        )
    ]
    pending.sort(
        key=lambda row: (
            row[0] in records,
            str(records.get(row[0], {}).get("checked_at", "")),
            row[1],
            row[5],
        )
    )
    budget = min(args.max_requests or policy.max_requests, policy.max_requests)
    report = {
        "source": source,
        "generated_at": utc_string(),
        "mapping_sha256": file_sha256(args.mapping_db),
        "catalog": catalog_stats,
        "candidate_count": len(candidates),
        "due_before_run": len(pending),
        "initial_unchecked_before_run": sum(k not in records for k, *_ in candidates),
        "budget": budget,
        "limits": {
            "per_second": policy.per_second,
            "per_minute": policy.per_minute,
            "per_hour": policy.per_hour,
            "delay_seconds": policy.delay_seconds,
        },
        "attempted": 0,
        "found": 0,
        "missing": 0,
        "warnings": [],
        "errors": [],
        "dry_run": args.dry_run,
    }
    target = args.output_dir / f"{source}.jsonl.gz"
    if getattr(args, "dry_run", False):
        report["preview_candidates"] = [
            {
                "anchor_id": anchor,
                "provider": provider,
                "native_title_id": native,
                "season": season,
                "episode": episode,
            }
            for _, anchor, provider, native, season, episode in pending[:10]
        ]
        return report, True
    if getattr(args, "export_only", False):
        report.update(export_external(source, state, catalog, target))
        report["initial_unchecked_after_run"] = report["initial_unchecked_before_run"]
        report["remaining_budget"] = budget
        report["due_after_run"] = len(pending)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{source}-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8"
        )
        return report, True
    remaining = [budget]
    limiter = PacedLimiter(policy)
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(20),
            follow_redirects=False,
            headers={"User-Agent": "anime-timestamp-db-crawler/0.2"},
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )
    success = True
    try:
        for key, _anchor, provider, native, season, episode in pending:
            if remaining[0] <= 0:
                report["stopped_reason"] = "request_budget_exhausted"
                break
            try:
                url, headers, params = make_request(
                    source, provider, native, season, episode, api_key=api_key
                )
                status, payload = await request_json(
                    client,
                    limiter,
                    remaining,
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                    allow_list=source == "introhater",
                    retry_429_wait_seconds=policy.retry_429_wait_seconds,
                    max_429_wait_seconds=policy.max_429_wait_seconds,
                )
                if status == 404:
                    segments: list[dict[str, Any]] = []
                else:
                    segments = parse_segments(
                        source,
                        payload,
                        provider=provider,
                        title_id=native,
                        season=season,
                        episode=episode,
                    )
                records[key] = {
                    "status": "found" if segments else "missing",
                    "checked_at": utc_string(),
                    "segments": segments,
                }
                report["found" if segments else "missing"] += 1
                report["attempted"] += 1
            except RateLimited as error:
                report["stopped_reason"] = "rate_limited_after_retry"
                report["retry_after_seconds"] = error.retry_after
                report["warnings"].append(
                    {
                        "candidate": key,
                        "type": "RateLimited",
                        "message": str(error),
                    }
                )
                break
            except BudgetExhausted:
                report["stopped_reason"] = "request_budget_exhausted"
                break
            except (ValueError, BadUpstreamResponse) as error:
                report["errors"].append(
                    {
                        "candidate": key,
                        "type": type(error).__name__,
                        "message": str(error)[:200],
                    }
                )
                success = False
                break
            if report["attempted"] % 25 == 0:
                write_gzip_json(state_path, state)
    finally:
        if owns_client:
            await client.aclose()
        write_gzip_json(state_path, state)
        report.update(export_external(source, state, catalog, target))
        report["remaining_budget"] = remaining[0]
        after = external_candidates(
            source,
            catalog,
            state,
            max_episodes=args.max_episodes,
            unknown_episodes=args.unknown_episodes,
        )
        report["candidate_count_after_run"] = len(after)
        report["initial_unchecked_after_run"] = sum(k not in records for k, *_ in after)
        report["due_after_run"] = sum(
            due(
                records.get(k),
                positive_days=args.positive_ttl_days,
                negative_days=args.negative_ttl_days,
            )
            for k, *_ in after
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{source}-report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", "utf-8"
        )
    return report, success
