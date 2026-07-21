from __future__ import annotations

from typing import Any


def parse_optional_limit(value: Any) -> int | None:
    """Parse CLI/API limits where omitted or "all" means uncapped.

    The function is intentionally small and shared by ETL/search/universe
    commands so "250" remains a deployment configuration choice rather than a
    hidden product ceiling.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text == "all":
        return None
    parsed = int(text)
    if parsed <= 0:
        raise ValueError("limit must be positive or 'all'")
    return parsed


def parse_optional_offset(value: Any) -> int:
    if value is None:
        return 0
    parsed = int(str(value).strip())
    if parsed < 0:
        raise ValueError("offset must be zero or greater")
    return parsed
