"""Consistent, transparent identification for timestamp crawler HTTP requests.

A descriptive User-Agent helps upstream operators recognize this project.
It does not solve or evade Cloudflare challenges.
"""

from __future__ import annotations

DEFAULT_CRAWLER_USER_AGENT = (
    "anime-timestamp-db/0.3 (+https://github.com/anime-db-project/anime-timestamp-db)"
)


def crawler_headers(user_agent: str | None = None) -> dict[str, str]:
    """Use a project-identifying User-Agent or an explicit operator override."""
    custom = (user_agent or "").strip()
    if custom and (
        len(custom) > 240 or any(ord(char) < 32 or ord(char) > 126 for char in custom)
    ):
        raise ValueError("User-Agent must be one printable ASCII line (1-240 chars)")
    return {
        "User-Agent": custom or DEFAULT_CRAWLER_USER_AGENT,
        "Accept": "application/json",
    }
