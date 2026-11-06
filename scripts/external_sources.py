"""Conservative adapters for third-party skip timestamp APIs.

These adapters never infer canonical MAL episode numbering from season/episode
coordinates. All imported observations retain original media identity/order.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any
from urllib.parse import quote

EXTERNAL_SOURCES = ("introdb", "publicmetadb", "theintrodb", "introhater")
PREFERRED_PROVIDER = {
    "introdb": ("imdb",),
    "publicmetadb": ("tmdb_tv",),
    "theintrodb": ("tvdb", "imdb", "tmdb_tv"),
    "introhater": ("imdb",),
}
URLS = {
    "introdb": "https://api.introdb.app/segments",
    "publicmetadb": "https://publicmetadb.com/api/external/skips",
    "theintrodb": "https://api.theintrodb.org/v4/media",
    "introhater": "https://introhater.com/api/segments",
}
SIMPLE_SEGMENT_TYPES = {
    "intro": "opening",
    "opening": "opening",
    "recap": "recap",
    "credits": "ending",
    "outro": "ending",
    "post_credits": "post_credits",
    "post-credits": "post_credits",
    "preview": "preview",
    "ending": "ending",
}
MAX_MS = 43_200_000


def _num(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    return round(v) if math.isfinite(v) and 0 <= v <= MAX_MS else None


def _range(start: Any, end: Any) -> tuple[int, int] | None:
    a, b = _num(start), _num(end)
    return (a, b) if a is not None and b is not None and a < b else None


def make_request(
    source: str,
    provider: str,
    title_id: str,
    season: int,
    episode: int,
    *,
    api_key: str = "",
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Fixed allowlisted HTTPS endpoints; no user-controlled destination."""
    if source not in EXTERNAL_SOURCES or provider not in PREFERRED_PROVIDER[source]:
        raise ValueError("unsupported provider ID for source")
    if not (season >= 0 and 1 <= episode <= 10_000):
        raise ValueError("invalid season or episode")
    if not title_id or any(c in title_id for c in "/?#&"):
        raise ValueError("invalid source title ID")
    headers: dict[str, str] = {}
    params: dict[str, Any] = {"season": season, "episode": episode}
    if source in ("introdb", "introhater"):
        if not (title_id.startswith("tt") and title_id[2:].isdigit()):
            raise ValueError("IMDb ID must be tt followed by digits")
        if source == "introhater":
            return (
                URLS[source] + "/" + quote(f"{title_id}:{season}:{episode}", safe=":"),
                headers,
                {},
            )
        params["imdb_id"] = title_id
    elif source == "publicmetadb":
        if not api_key:
            raise ValueError("PUBLICMETADB_API_KEY is required")
        headers["Authorization"] = "Bearer " + api_key
        params["tmdb_id"] = title_id
        # The API now requires the TMDB namespace as well as the TMDB ID.
        params["media_type"] = "tv"
    else:
        params[
            {"tvdb": "tvdb_id", "imdb": "imdb_id", "tmdb_tv": "tmdb_id"}[provider]
        ] = title_id
    return URLS[source], headers, params


def parse_segments(
    source: str,
    payload: dict[str, Any] | list[Any],
    *,
    provider: str,
    title_id: str,
    season: int,
    episode: int,
) -> list[dict[str, Any]]:
    """Read only bounded explicit start+end timestamps. Never guess end of video."""
    if source not in EXTERNAL_SOURCES:
        raise ValueError("unknown timestamp source")
    results: list[tuple[str, int, int, str, str]] = []

    def emit(
        kind: str, start: Any, end: Any, *, origin: str = "", key: str = ""
    ) -> None:
        canonical = SIMPLE_SEGMENT_TYPES.get(str(kind).strip().casefold())
        bounds = _range(start, end)
        if canonical and bounds:
            # Separate mirrors are not independent evidence. Preserve source
            # identity for review and possible later deduplication.
            results.append((canonical, *bounds, str(origin), str(key)))

    if source == "introdb" and isinstance(payload, dict):
        for upstream_kind, normalized in (
            ("intro", "intro"),
            ("recap", "recap"),
            ("outro", "outro"),
            ("post_credits", "post_credits"),
        ):
            slot = payload.get(upstream_kind)
            if isinstance(slot, dict):
                emit(normalized, slot.get("start_ms"), slot.get("end_ms"))
    elif source == "theintrodb" and isinstance(payload, dict):
        for name in ("intro", "recap", "credits", "preview"):
            slots = payload.get(name) or []
            if isinstance(slots, list):
                for idx, item in enumerate(slots):
                    if isinstance(item, dict):
                        emit(
                            name,
                            0 if item.get("start_ms") is None else item.get("start_ms"),
                            item.get("end_ms"),
                            key=str(idx),
                        )
    elif source == "publicmetadb" and isinstance(payload, dict):
        for label, field in (
            ("intro", "intro"),
            ("recap", "recap"),
            ("credits", "credits"),
            ("preview", "preview"),
        ):
            emit(
                label, payload.get(f"{field}_start_ms"), payload.get(f"{field}_end_ms")
            )
    elif source == "introhater" and isinstance(payload, list):
        for idx, item in enumerate(payload):
            if not isinstance(item, dict):
                continue
            if (
                item.get("videoId")
                and str(item["videoId"]) != f"{title_id}:{season}:{episode}"
            ):
                continue
            origin = str(item.get("source") or "unknown")
            if "auto-import" in (item.get("contributors") or []):
                origin = f"mirrored:{origin}"
            emit(
                item.get("label") or "Intro",
                _seconds_to_ms(item.get("start")),
                _seconds_to_ms(item.get("end")),
                origin=origin,
                key=str(idx),
            )
    else:
        raise ValueError(f"unexpected {source} response schema")

    rows = []
    for kind, start, end, origin, identifier in results:
        digest = hashlib.sha256(
            json.dumps(
                [
                    source,
                    provider,
                    title_id,
                    season,
                    episode,
                    kind,
                    start,
                    end,
                    origin,
                    identifier,
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()[:32]
        rows.append(
            {
                "source": source,
                "native_provider": provider,
                "native_title_id": title_id,
                "season": season,
                "episode": episode,
                "type": kind,
                "start_ms": start,
                "end_ms": end,
                "duration_ms": None,
                "source_segment_id": digest,
                "upstream_lineage": origin or source,
                "episode_identity_proven": False,
                "source_episode_key": f"{season}:{episode}",
            }
        )
    return rows


def _seconds_to_ms(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        x = float(value) * 1000
    except (ValueError, TypeError):
        return None
    return round(x) if math.isfinite(x) and 0 <= x <= MAX_MS else None
