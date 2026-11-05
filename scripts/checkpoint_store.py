"""Durable GitHub branch checkpoints for incremental API crawling.

The source-specific branch is a public audit/recovery store, not a release. Keep
source credentials and user identifiers out of it. GitHub Actions cache remains
only an optimization, and artifacts are short-lived debugging copies.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

BRANCH_PREFIX = "crawler-state-"
MAX_STATE_BYTES = 20_000_000


def _github(method: str, endpoint: str, payload: dict | None = None) -> dict | None:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to access durable checkpoints")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not repository or repository.count("/") != 1:
        raise RuntimeError("GITHUB_REPOSITORY must be owner/repository")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    url = "https://api.github.com/repos/" + repository + "/" + endpoint
    req = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "anime-timestamp-db-state-manager",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=60) as response:
            result = response.read()
    except HTTPError as exc:
        if exc.code == 404 and method == "GET":
            return None
        raise RuntimeError(
            f"GitHub checkpoint API {method} {endpoint.split('?')[0]} "
            f"returned HTTP {exc.code}"
        ) from None
    return json.loads(result) if result else {}


def _branch(source: str) -> str:
    # This utility is invoked directly by Actions and also imported as a
    # package. Keep branch validation independent of import search paths.
    if source not in (
        "aniskip",
        "anime_skip",
        "introdb",
        "publicmetadb",
        "theintrodb",
        "introhater",
    ):
        raise ValueError(f"Unknown source {source!r}")
    return BRANCH_PREFIX + source


def _path(source: str) -> str:
    return "checkpoints/" + source + ".json.gz"


def _ref_exists(source: str) -> bool:
    return _github("GET", "git/ref/heads/" + _branch(source)) is not None


def _get(source: str) -> tuple[bytes, str] | None:
    ref = _branch(source)
    response = _github(
        "GET",
        f"contents/{_path(source)}?ref={quote(ref, safe='')}",
    )
    if response is None:
        return None
    encoded = response.get("content") or ""
    if not encoded:
        blob = _github("GET", f"git/blobs/{response['sha']}")
        if blob is None or blob.get("encoding") != "base64":
            raise RuntimeError("GitHub checkpoint blob not readable")
        encoded = blob["content"]
    return base64.b64decode(encoded), response["sha"]


def _validate(data: bytes, source: str) -> dict:
    if len(data) > MAX_STATE_BYTES:
        raise ValueError("Checkpoint too large; split the state into shards")
    try:
        state = json.loads(gzip.decompress(data))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Corrupted or invalid gzip JSON checkpoint") from exc
    if (
        not isinstance(state, dict)
        or state.get("version") != 1
        or state.get("source") != source
        or not isinstance(state.get("records"), dict)
    ):
        raise ValueError("Checkpoint format or source does not match")
    return state


def restore(source: str, target: Path) -> dict:
    exists = _ref_exists(source)
    if not exists:
        return {"source": source, "restored": False, "reason": "initial bootstrap"}
    item = _get(source)
    if item is None:
        raise RuntimeError(
            f"Durable branch {_branch(source)} exists but checkpoint is missing; "
            "refusing to silently restart from an empty state"
        )
    data, _sha = item
    state = _validate(data, source)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        part.write_bytes(data)
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return {
        "source": source,
        "restored": True,
        "records": len(state["records"]),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def persist(source: str, target: Path) -> dict:
    if not target.is_file():
        raise FileNotFoundError(target)
    data = target.read_bytes()
    state = _validate(data, source)
    if not _ref_exists(source):
        head = os.environ.get("GITHUB_SHA", "")
        if len(head) != 40:
            raise RuntimeError("GITHUB_SHA is required to create checkpoint branch")
        _github(
            "POST",
            "git/refs",
            {"ref": "refs/heads/" + _branch(source), "sha": head},
        )
    old = _get(source)
    if old is not None and old[0] == data:
        return {"source": source, "changed": False, "records": len(state["records"])}
    body = {
        "message": f"checkpoint({source}): persist {len(state['records'])} API checks",
        "content": base64.b64encode(data).decode("ascii"),
        "branch": _branch(source),
    }
    if old is not None:
        body["sha"] = old[1]
    _github("PUT", "contents/" + _path(source), body)
    # Re-read the committed bytes to prevent reporting success if storage failed.
    written = _get(source)
    if written is None or written[0] != data:
        raise RuntimeError("Durable checkpoint verification failed")
    return {
        "source": source,
        "changed": True,
        "records": len(state["records"]),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("restore", "persist"))
    parser.add_argument("--source", required=True, choices=("aniskip", "anime_skip"))
    parser.add_argument(
        "--state-dir", type=Path, default=Path(".build-cache/crawler-state")
    )
    args = parser.parse_args()
    file = args.state_dir / (args.source + ".json.gz")
    result = (
        restore(args.source, file)
        if args.operation == "restore"
        else persist(args.source, file)
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
