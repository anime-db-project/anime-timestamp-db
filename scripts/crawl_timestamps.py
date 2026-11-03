"""Incremental, read-only collectors for AniSkip and Anime Skip.

This is a separate ingest stage: its checkpoints and responses NEVER enter the
published SQLite databases. The output is a reviewable JSONL snapshot, not an
automatically published redistributable dataset.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import math
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from anime_timestamp_db.mapping_identity import mapping_database_metadata

DEFAULT_RPM = 70
ANISKIP_TYPES = ("op", "ed", "mixed-op", "mixed-ed", "recap")
ANISKIP_KIND = {
    "op": "opening",
    "ed": "ending",
    "mixed-op": "mixed-opening",
    "mixed-ed": "mixed-ending",
    "recap": "recap",
}
ANIME_SKIP_KIND = {
    "intro": "opening",
    "new intro": "opening",
    "mixed intro": "mixed-opening",
    "recap": "recap",
    "filler": "filler",
    "credits": "ending",
    "new credits": "ending",
    "mixed credits": "mixed-ending",
    "preview": "preview",
    "transition": "transition",
    "branding": "branding",
    "title card": "title_card",
}
GRAPHQL = """
query AnimeTimestampCrawler($id: String!) {
  findShowsByExternalId(service: ANILIST, serviceId: $id) {
    id
    episodes {
      id season number absoluteNumber baseDuration
      timestamps { id at source type { name } }
    }
  }
}
"""


def now() -> datetime:
    return datetime.now(UTC)


def utc_string() -> str:
    return now().isoformat()


def positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        integer = int(value)
    except (ValueError, TypeError):
        return None
    return integer if integer > 0 and str(value).strip() == str(integer) else None


def nonnegative_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def as_ms(value: Any) -> int | None:
    number = nonnegative_number(value)
    return round(number * 1000) if number is not None else None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def load_catalog(path: Path) -> tuple[dict[int, dict[str, str]], dict[str, int]]:
    """Read only explicit accepted node memberships from the published mapping DB."""
    mapping_database_metadata(path)
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    duplicates: set[tuple[int, str]] = set()
    # Never assign a native provider ID shared between distinct AMDB anchors.
    external_owners: dict[tuple[str, str], int] = {}
    ambiguous_external_ids: set[tuple[str, str]] = set()
    candidates: dict[int, dict[str, str]] = defaultdict(dict)
    try:
        for anchor, provider, external in conn.execute(
            """SELECT e.anchor_id, n.provider, n.external_id
               FROM entities AS e
               JOIN entity_nodes AS en ON en.entity_id=e.entity_id
               JOIN nodes AS n ON n.id=en.node_id
               WHERE n.provider IN ('mal', 'anilist')
               ORDER BY e.anchor_id, n.provider, n.external_id"""
        ):
            anchor = int(anchor)
            provider = str(provider)
            external = str(external).strip()
            if positive_int(external) is None:
                continue
            native_key = (provider, external)
            owner = external_owners.setdefault(native_key, anchor)
            if owner != anchor:
                ambiguous_external_ids.add(native_key)
            existing = candidates[anchor].get(provider)
            if existing is not None and existing != external:
                duplicates.add((anchor, provider))
            else:
                candidates[anchor][provider] = external
    finally:
        conn.close()
    for anchor, provider in duplicates:
        candidates[anchor].pop(provider, None)
    for ids in candidates.values():
        for provider, external in tuple(ids.items()):
            if (provider, external) in ambiguous_external_ids:
                ids.pop(provider)
    return dict(candidates), {
        "anchors": len(candidates),
        "ambiguous_provider_keys": len(duplicates),
        "ambiguous_external_ids": len(ambiguous_external_ids),
        "mal_titles": sum("mal" in ids for ids in candidates.values()),
        "anilist_titles": sum("anilist" in ids for ids in candidates.values()),
    }


def mal_episode_hints(path: Path | None) -> dict[int, set[int]]:
    """Only provider-confirmed MAL episode numbering is safe for AniSkip."""
    result: dict[int, set[int]] = defaultdict(set)
    if path is None:
        return result
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        role = conn.execute(
            "SELECT value FROM metadata WHERE key='database_role'"
        ).fetchone()
        if role != ("runtime",):
            raise ValueError("Timestamp episode hints require a runtime timestamps.db")
        for anchor, text in conn.execute(
            """SELECT anchor_id, episode_number_text
               FROM episode_ids WHERE provider='mal' AND scope=''"""
        ):
            n = positive_int(text)
            if n is not None:
                result[int(anchor)].add(n)
    finally:
        conn.close()
    return result


class RateLimited(Exception):
    pass


class BadUpstreamResponse(Exception):
    pass


class UpstreamBrokenReference(BadUpstreamResponse):
    """A single Anime Skip title references missing backend rows."""


class BudgetExhausted(Exception):
    pass


class Limiter:
    """Sliding 60-second window shared by every retry of one source job."""

    def __init__(self, rpm: int):
        if rpm < 1 or rpm > 120:
            raise ValueError("rpm must be between 1 and 120")
        self.rpm = rpm
        self.calls: deque[float] = deque()

    async def wait(self) -> None:
        current = time.monotonic()
        while self.calls and current - self.calls[0] >= 60:
            self.calls.popleft()
        if len(self.calls) >= self.rpm:
            await asyncio.sleep(max(0.0, 60 - (current - self.calls[0]) + 0.05))
            current = time.monotonic()
            while self.calls and current - self.calls[0] >= 60:
                self.calls.popleft()
        self.calls.append(time.monotonic())


async def request_json(
    client: httpx.AsyncClient,
    limiter: Limiter,
    budget: list[int],
    method: str,
    url: str,
    **kwargs: Any,
) -> tuple[int, dict[str, Any]]:
    for attempt in range(3):
        if budget[0] <= 0:
            raise BudgetExhausted("request budget exhausted")
        await limiter.wait()
        budget[0] -= 1
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TransportError as error:
            if attempt == 2:
                raise BadUpstreamResponse(
                    f"transport: {type(error).__name__}"
                ) from error
            await asyncio.sleep(2**attempt)
            continue
        if response.status_code in (429, 403):
            raise RateLimited(
                f"HTTP {response.status_code}; Retry-After={response.headers.get('retry-after', 'not supplied')}"
            )
        if response.status_code >= 500:
            if attempt == 2:
                raise BadUpstreamResponse(f"HTTP {response.status_code}")
            await asyncio.sleep(2**attempt)
            continue
        if response.status_code not in (200, 404):
            raise BadUpstreamResponse(
                f"HTTP {response.status_code}: {response.text[:150]}"
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise BadUpstreamResponse("non-JSON response") from error
        if not isinstance(payload, dict):
            raise BadUpstreamResponse("response is not an object")
        return response.status_code, payload
    raise AssertionError("unreachable")


def parse_aniskip(
    payload: dict[str, Any], mal_id: str, episode: int
) -> list[dict[str, Any]]:
    observations = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        kind = ANISKIP_KIND.get(str(item.get("skipType", "")).casefold())
        interval = item.get("interval")
        if not kind or not isinstance(interval, dict):
            continue
        start = as_ms(interval.get("startTime"))
        end = as_ms(interval.get("endTime"))
        if start is None or end is None or end <= start:
            continue
        duration = as_ms(item.get("episodeLength"))
        observations.append(
            {
                "source": "aniskip",
                "native_title_id": mal_id,
                "episode": episode,
                "type": kind,
                "start_ms": start,
                "end_ms": end,
                "duration_ms": duration if duration and duration > 0 else None,
                "source_segment_id": str(item.get("skipId") or ""),
                "upstream_lineage": "aniskip",
            }
        )
    return observations


def parse_anime_skip(payload: dict[str, Any], anilist_id: str) -> list[dict[str, Any]]:
    errors = payload.get("errors")
    if errors:
        # Anime Skip can return partial GraphQL data when a referenced
        # timestamp row has disappeared. Do not import incomplete title data.
        if isinstance(errors, list) and all(
            isinstance(error, dict)
            and str(error.get("message") or "").startswith("Row not found in id=")
            for error in errors
        ):
            raise UpstreamBrokenReference(
                "Anime Skip referenced missing timestamp row(s)"
            )
        raise BadUpstreamResponse("GraphQL returned errors: " + str(errors)[:180])
    data = payload.get("data")
    shows = data.get("findShowsByExternalId") if isinstance(data, dict) else None
    if not isinstance(shows, list):
        raise BadUpstreamResponse("missing findShowsByExternalId array")
    observations: list[dict[str, Any]] = []
    for show in shows:
        if not isinstance(show, dict):
            continue
        for ep in show.get("episodes") or []:
            if not isinstance(ep, dict):
                continue
            absolute_number = positive_int(ep.get("absoluteNumber"))
            season = positive_int(ep.get("season"))
            season_number = positive_int(ep.get("number"))
            episode = absolute_number or season_number
            if episode is None:
                continue
            # "number" can repeat in multiple seasons. Only a stable absolute
            # number or an explicit first-season number may be normalized.
            identity_proven = absolute_number is not None or season == 1
            duration = as_ms(ep.get("baseDuration"))
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for point in ep.get("timestamps") or []:
                if not isinstance(point, dict) or not isinstance(
                    point.get("type"), dict
                ):
                    continue
                at = as_ms(point.get("at"))
                if at is None:
                    continue
                source = str(point.get("source") or "UNKNOWN").strip().upper()
                grouped[source].append(
                    {
                        "at_ms": at,
                        "kind": point["type"].get("name"),
                        "id": str(point.get("id") or ""),
                    }
                )
            for raw_source, points in grouped.items():
                points.sort(key=lambda item: item["at_ms"])
                for i, point in enumerate(points):
                    kind = ANIME_SKIP_KIND.get(str(point["kind"] or "").casefold())
                    end = points[i + 1]["at_ms"] if i + 1 < len(points) else duration
                    if kind is None or end is None or end <= point["at_ms"]:
                        continue
                    observations.append(
                        {
                            "source": "anime_skip",
                            "native_title_id": anilist_id,
                            "episode": episode,
                            "type": kind,
                            "start_ms": point["at_ms"],
                            "end_ms": end,
                            "duration_ms": duration
                            if duration and duration > 0
                            else None,
                            "source_segment_id": point["id"],
                            "upstream_lineage": raw_source,
                            "upstream_episode_id": str(ep.get("id") or ""),
                            "season": season,
                            "absolute_number": absolute_number,
                            "season_episode_number": season_number,
                            "episode_identity_proven": identity_proven,
                        }
                    )
    return observations


def load_state(path: Path, source: str) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "source": source, "records": {}}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    if (
        not isinstance(data, dict)
        or data.get("version") != 1
        or data.get("source") != source
        or not isinstance(data.get("records"), dict)
    ):
        raise ValueError(f"Invalid crawler checkpoint {path}")
    return data


def write_gzip_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    try:
        # Deterministic gzip: no current-time header and no temporary path.
        # Identical checkpoint data must not cause a new branch commit or a
        # new release solely because of gzip metadata.
        payload = json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        with part.open("wb") as handle:
            with gzip.GzipFile(
                fileobj=handle, mode="wb", filename="", mtime=0, compresslevel=6
            ) as compressed:
                compressed.write(payload)
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def due(record: Any, *, positive_days: int, negative_days: int) -> bool:
    if not isinstance(record, dict):
        return True
    try:
        retry_at = datetime.fromisoformat(record["retry_after_at"])
        if retry_at.tzinfo is not None and now() < retry_at:
            return False
    except (KeyError, TypeError, ValueError):
        pass
    try:
        checked = datetime.fromisoformat(record["checked_at"])
        if checked.tzinfo is None:
            return True
    except (KeyError, TypeError, ValueError):
        return True
    days = positive_days if record.get("status") == "found" else negative_days
    return checked + timedelta(days=days) <= now()


def candidates(
    source: str,
    catalog: dict[int, dict[str, str]],
    hints: dict[int, set[int]],
    *,
    unknown_episodes: int,
    max_episodes: int,
) -> list[tuple[str, int, str, int | None]]:
    """A title stays eligible even if another timestamp source already covers it."""
    result: list[tuple[str, int, str, int | None]] = []
    provider = "mal" if source == "aniskip" else "anilist"
    for anchor, ids in sorted(catalog.items()):
        native_id = ids.get(provider)
        if native_id is None:
            continue
        if source == "anime_skip":
            result.append((native_id, anchor, native_id, None))
            continue
        confirmed = hints.get(anchor, set())
        if confirmed:
            top = min(max_episodes, max(confirmed) + 2)
            # The upper bound also prevents unbounded guessing for long-running series.
            episodes = set(range(1, top + 1)) | confirmed
        else:
            episodes = set(range(1, unknown_episodes + 1))
        for episode in sorted(episodes):
            result.append((f"{native_id}:{episode}", anchor, native_id, episode))
    return result


def export_snapshot(
    source: str,
    state: dict[str, Any],
    catalog: dict[int, dict[str, str]],
    target: Path,
) -> dict[str, int]:
    """Resolve fresh AMDB anchors at export; never trust cached anchor assignments."""
    provider = "mal" if source == "aniskip" else "anilist"
    by_id = {
        ids[provider]: anchor for anchor, ids in catalog.items() if provider in ids
    }
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, record in sorted(state["records"].items()):
        if not isinstance(record, dict) or record.get("status") != "found":
            continue
        if source == "aniskip":
            parts = key.split(":")
            if len(parts) != 2 or positive_int(parts[0]) is None:
                continue
            checked_episode = positive_int(parts[1])
            if checked_episode is None:
                continue
            native_id = parts[0]
        else:
            if positive_int(key) is None:
                continue
            native_id = key
            checked_episode = None
        anchor = by_id.get(native_id)
        if anchor is None:
            continue
        for segment in record.get("segments", []):
            if not isinstance(segment, dict):
                continue
            if (
                segment.get("native_title_id") != native_id
                or segment.get("source") != source
                or positive_int(segment.get("episode")) is None
                or (
                    checked_episode is not None
                    and positive_int(segment.get("episode")) != checked_episode
                )
            ):
                continue
            row = dict(segment)
            row["anchor_id"] = anchor
            row["episode_key"] = f"ep:{segment['episode']}"
            if not row.get("source_segment_id"):
                digest = hashlib.sha256(
                    json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                row["source_segment_id"] = f"derived:{digest[:32]}"
            identity = (
                row["upstream_lineage"],
                row["source_segment_id"],
                anchor,
                row["episode_key"],
            )
            identity_key = json.dumps(identity, sort_keys=True)
            if identity_key in seen:
                continue
            seen.add(identity_key)
            rows.append(row)
    rows.sort(
        key=lambda row: (
            row["anchor_id"],
            row["episode"],
            row["type"],
            row["start_ms"],
            row["source_segment_id"],
        )
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return {
        "observations": len(rows),
        "titles": len({row["anchor_id"] for row in rows}),
    }


async def crawl(
    args: argparse.Namespace,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[dict[str, Any], bool]:
    source = args.source
    catalog, catalog_stats = load_catalog(args.mapping_db)
    only_anchor = getattr(args, "only_anchor", None)
    if only_anchor is not None:
        if only_anchor not in catalog:
            raise ValueError(
                f"AMDB anchor {only_anchor} is not in the MAL/AniList catalog"
            )
        catalog = {only_anchor: catalog[only_anchor]}
    state_path = args.state_dir / f"{source}.json.gz"
    state = load_state(state_path, source)
    records: dict[str, Any] = state["records"]
    hints = mal_episode_hints(args.timestamps_db) if source == "aniskip" else {}
    if source == "aniskip":
        # Existing API observations are also confirmed positive episode hints.
        # Without this, titles without a static episode index never advance
        # beyond the initial 1-2 episode discovery probe.
        by_mal = {ids["mal"]: anchor for anchor, ids in catalog.items() if "mal" in ids}
        for record in records.values():
            if not isinstance(record, dict) or record.get("status") != "found":
                continue
            for segment in record.get("segments", []):
                if not isinstance(segment, dict):
                    continue
                anchor = by_mal.get(str(segment.get("native_title_id")))
                episode = positive_int(segment.get("episode"))
                if anchor is not None and episode is not None:
                    hints.setdefault(anchor, set()).add(episode)
    all_candidates = candidates(
        source,
        catalog,
        hints,
        unknown_episodes=args.unknown_episodes,
        max_episodes=args.max_episodes,
    )
    pending = [
        item
        for item in all_candidates
        if due(
            records.get(item[0]),
            positive_days=args.positive_ttl_days,
            negative_days=args.negative_ttl_days,
        )
    ]
    # New identities first, then the oldest due rechecks.
    pending.sort(
        key=lambda item: (
            item[0] in records,
            str(records.get(item[0], {}).get("checked_at", "")),
            item[1],
            item[3] or 0,
        )
    )
    report: dict[str, Any] = {
        "source": source,
        "generated_at": utc_string(),
        "mapping_sha256": file_sha256(args.mapping_db),
        "catalog": catalog_stats,
        "candidate_count": len(all_candidates),
        "due_before_run": len(pending),
        "initial_unchecked_before_run": sum(
            item[0] not in records for item in all_candidates
        ),
        "rpm": args.rpm,
        "budget": args.max_requests,
        "attempted": 0,
        "found": 0,
        "missing": 0,
        "skipped_upstream_invalid": 0,
        "warnings": [],
        "errors": [],
        "dry_run": args.dry_run,
    }
    if getattr(args, "export_only", False):
        output = args.output_dir / f"{source}.jsonl.gz"
        report.update(export_snapshot(source, state, catalog, output))
        report["initial_unchecked_after_run"] = report["initial_unchecked_before_run"]
        report["remaining_budget"] = args.max_requests
        report["due_after_run"] = len(pending)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{source}-report.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return report, True
    if args.dry_run:
        report["preview_candidates"] = [
            {"anchor_id": anchor, "native_title_id": native, "episode": ep}
            for _key, anchor, native, ep in pending[:10]
        ]
        return report, True

    remaining = [args.max_requests]
    limiter = Limiter(args.rpm)
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(20),
            follow_redirects=True,
            headers={"User-Agent": "anime-timestamp-db-crawler/0.1"},
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )
    success = True
    try:
        for key, _anchor, native_id, episode in pending:
            if remaining[0] <= 0:
                break
            try:
                if source == "aniskip":
                    assert episode is not None
                    url = f"https://api.aniskip.com/v2/skip-times/{native_id}/{episode}"
                    params = [("types", kind) for kind in ANISKIP_TYPES]
                    params.append(("episodeLength", "0"))
                    status, payload = await request_json(
                        client,
                        limiter,
                        remaining,
                        "GET",
                        url,
                        params=params,
                    )
                    if status == 404 and payload.get("found") is not False:
                        raise BadUpstreamResponse("unexpected AniSkip 404")
                    segments = parse_aniskip(payload, native_id, episode)
                else:
                    if not args.anime_skip_client_id:
                        raise ValueError(
                            "ANIME_SKIP_CLIENT_ID is required for Anime Skip"
                        )
                    status, payload = await request_json(
                        client,
                        limiter,
                        remaining,
                        "POST",
                        f"{args.anime_skip_url.rstrip('/')}/graphql",
                        headers={"X-Client-ID": args.anime_skip_client_id},
                        json={
                            "query": GRAPHQL,
                            "operationName": "AnimeTimestampCrawler",
                            "variables": {"id": native_id},
                        },
                    )
                    if status != 200:
                        raise BadUpstreamResponse(
                            f"unexpected Anime Skip HTTP {status}"
                        )
                    segments = parse_anime_skip(payload, native_id)
                records[key] = {
                    "status": "found" if segments else "missing",
                    "checked_at": utc_string(),
                    "segments": segments,
                }
                report["found" if segments else "missing"] += 1
                report["attempted"] += 1
            except UpstreamBrokenReference as error:
                # Keep valid previously collected segments if this is a recheck.
                # An API-side broken reference is not a missing title and must
                # not stop independent title lookups.
                checked_at = utc_string()
                retry_after_at = (
                    now() + timedelta(days=args.negative_ttl_days)
                ).isoformat()
                existing = records.get(key)
                if not isinstance(existing, dict) or existing.get("status") not in (
                    "found",
                    "missing",
                ):
                    existing = {
                        "status": "source_error",
                        "checked_at": checked_at,
                        "segments": [],
                    }
                existing["retry_after_at"] = retry_after_at
                existing["last_error_at"] = checked_at
                existing["last_error_code"] = "upstream_broken_reference"
                records[key] = existing
                report["skipped_upstream_invalid"] += 1
                if len(report["warnings"]) < 100:
                    report["warnings"].append(
                        {
                            "candidate": key,
                            "type": type(error).__name__,
                            "message": str(error),
                        }
                    )
                report["attempted"] += 1
            except BudgetExhausted:
                break
            except (BadUpstreamResponse, RateLimited, ValueError) as error:
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
        output = args.output_dir / f"{source}.jsonl.gz"
        report.update(export_snapshot(source, state, catalog, output))
        report["remaining_budget"] = remaining[0]
        if source == "aniskip":
            for record in records.values():
                if not isinstance(record, dict) or record.get("status") != "found":
                    continue
                for segment in record.get("segments", []):
                    if not isinstance(segment, dict):
                        continue
                    anchor = by_mal.get(str(segment.get("native_title_id")))
                    episode = positive_int(segment.get("episode"))
                    if anchor is not None and episode is not None:
                        hints.setdefault(anchor, set()).add(episode)
            all_candidates = candidates(
                source,
                catalog,
                hints,
                unknown_episodes=args.unknown_episodes,
                max_episodes=args.max_episodes,
            )
        report["candidate_count_after_run"] = len(all_candidates)
        report["initial_unchecked_after_run"] = sum(
            item[0] not in records for item in all_candidates
        )
        report["due_after_run"] = sum(
            due(
                records.get(item[0]),
                positive_days=args.positive_ttl_days,
                negative_days=args.negative_ttl_days,
            )
            for item in all_candidates
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / f"{source}-report.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    return report, success


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("aniskip", "anime_skip"), required=True)
    parser.add_argument("--mapping-db", type=Path, required=True)
    parser.add_argument("--timestamps-db", type=Path, default=None)
    parser.add_argument(
        "--state-dir", type=Path, default=Path(".build-cache/crawler-state")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("crawler-output"))
    parser.add_argument("--rpm", type=int, default=DEFAULT_RPM)
    parser.add_argument("--max-requests", type=int, default=1000)
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Export a validated existing checkpoint without network requests",
    )
    parser.add_argument(
        "--only-anchor",
        type=int,
        default=None,
        help="Limit a test run to one AMDB anchor",
    )
    parser.add_argument("--max-episodes", type=int, default=96)
    parser.add_argument("--unknown-episodes", type=int, default=2)
    parser.add_argument("--positive-ttl-days", type=int, default=30)
    parser.add_argument("--negative-ttl-days", type=int, default=14)
    parser.add_argument("--anime-skip-url", default="https://anime-skip.com/api")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    args.anime_skip_client_id = os.getenv("ANIME_SKIP_CLIENT_ID", "").strip()
    if not (1 <= args.rpm <= 120):
        parser.error("--rpm must be from 1 to 120")
    if args.max_requests < 1 or args.unknown_episodes < 1 or args.max_episodes < 1:
        parser.error("request and episode bounds must be positive")
    if args.positive_ttl_days < 1 or args.negative_ttl_days < 1:
        parser.error("TTLs must be positive")
    if (
        args.source == "anime_skip"
        and not args.anime_skip_client_id
        and not args.dry_run
    ):
        parser.error("Set ANIME_SKIP_CLIENT_ID as an environment variable")
    report, success = asyncio.run(crawl(args))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
