from __future__ import annotations

import math


def normalize_episode_number(value: int | float | str) -> str:
    """Return one stable numeric episode token without truncating fractions."""

    if isinstance(value, bool):
        raise ValueError("episode number must be numeric")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("episode number must be finite")
        return str(int(value)) if value.is_integer() else format(value, ".15g")

    text = str(value).strip()
    if not text:
        raise ValueError("episode number must not be empty")
    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"episode number must be numeric: {value!r}") from exc
    if not math.isfinite(parsed):
        raise ValueError("episode number must be finite")
    return str(int(parsed)) if parsed.is_integer() else format(parsed, ".15g")
