from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_manifest(*, mode: str, requested_limit: int | None, rows: list[dict[str, Any]],
                   source: str, warnings: list[str] | None = None) -> dict[str, Any]:
    supported = [row for row in rows if row.get("isSupported")]
    unsupported = [row for row in rows if not row.get("isSupported")]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "createdAt": utc_now(),
        "universeMode": mode,
        "requestedLimit": requested_limit,
        "source": source,
        "companyCount": len(rows),
        "supportedCount": len(supported),
        "unsupportedCount": len(unsupported),
        "exchanges": sorted({row.get("exchange") for row in rows if row.get("exchange")}),
        "tickersIncluded": [row["ticker"] for row in supported],
        "warnings": warnings or [],
    }

