from __future__ import annotations

import re
from typing import Any

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def _tokens(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(text.lower()))


def _similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def _section(row: dict[str, Any]) -> str:
    return row.get("sectionKey") or row.get("item") or ""


def diversify_results(ranked: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Apply deterministic diversity after scoring; never modify BM25 scores."""
    if not ranked or limit < 1:
        return []
    selected = [ranked[0]]
    used = {ranked[0]["id"]}

    def acceptable(row: dict[str, Any]) -> bool:
        return all(_similarity(row.get("text", ""), chosen.get("text", "")) <= .70 for chosen in selected)

    for row in ranked[1:]:
        if len(selected) >= limit:
            break
        if row["score"] < ranked[0]["score"] * .25 or row["id"] in used or not acceptable(row):
            continue
        if not any(_section(chosen) == _section(row) for chosen in selected):
            selected.append(row); used.add(row["id"])
    for row in ranked[1:]:
        if len(selected) >= limit:
            break
        if row["id"] not in used and acceptable(row):
            selected.append(row); used.add(row["id"])
    return selected
