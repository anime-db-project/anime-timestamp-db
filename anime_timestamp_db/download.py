from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from anime_timestamp_db.config import SourceSpec

USER_AGENT = (
    "anime-timestamp-db/0.2 (+https://github.com/anime-db-project/anime-timestamp-db)"
)


@dataclass(frozen=True, slots=True)
class DownloadedSource:
    key: str
    path: Path
    source_url: str
    final_url: str
    sha256: str
    size_bytes: int
    retrieved_at: str
    etag: str
    last_modified: str
    from_cache: bool

    def manifest_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["path"] = self.path.name
        return data


def _safe_suffix(url: str) -> str:
    name = Path(urlparse(url).path).name
    suffixes = Path(name).suffixes
    return "".join(suffixes[-2:]) if suffixes else ".bin"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_meta(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def download_source(
    spec: SourceSpec,
    cache_dir: Path,
    *,
    force: bool = False,
    retries: int = 3,
) -> DownloadedSource:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload_path = cache_dir / f"{spec.key}{_safe_suffix(spec.url)}"
    meta_path = cache_dir / f"{spec.key}.download.json"
    old_meta = _load_meta(meta_path)

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if not force and payload_path.is_file():
        etag = str(old_meta.get("etag") or "")
        modified = str(old_meta.get("last_modified") or "")
        if etag:
            headers["If-None-Match"] = etag
        if modified:
            headers["If-Modified-Since"] = modified

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=httpx.Timeout(120.0, connect=30.0),
                headers=headers,
            ) as client:
                with client.stream("GET", spec.url) as response:
                    if response.status_code == 304 and payload_path.is_file():
                        return DownloadedSource(
                            key=spec.key,
                            path=payload_path,
                            source_url=spec.url,
                            final_url=str(old_meta.get("final_url") or spec.url),
                            sha256=str(
                                old_meta.get("sha256") or _sha256_file(payload_path)
                            ),
                            size_bytes=payload_path.stat().st_size,
                            retrieved_at=str(old_meta.get("retrieved_at") or ""),
                            etag=str(old_meta.get("etag") or ""),
                            last_modified=str(old_meta.get("last_modified") or ""),
                            from_cache=True,
                        )
                    response.raise_for_status()
                    tmp_path = payload_path.with_suffix(payload_path.suffix + ".part")
                    digest = hashlib.sha256()
                    size = 0
                    with tmp_path.open("wb") as handle:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                    os.replace(tmp_path, payload_path)
                    now = datetime.now(UTC).isoformat()
                    result = DownloadedSource(
                        key=spec.key,
                        path=payload_path,
                        source_url=spec.url,
                        final_url=str(response.url),
                        sha256=digest.hexdigest(),
                        size_bytes=size,
                        retrieved_at=now,
                        etag=response.headers.get("etag", ""),
                        last_modified=response.headers.get("last-modified", ""),
                        from_cache=False,
                    )
                    meta_path.write_text(
                        json.dumps(result.manifest_dict(), indent=2, sort_keys=True),
                        "utf-8",
                    )
                    return result
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(float(attempt * 2))

    assert last_error is not None
    raise RuntimeError(f"Could not download {spec.key} from {spec.url}: {last_error}")
