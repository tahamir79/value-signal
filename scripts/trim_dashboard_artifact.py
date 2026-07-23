from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_json import write_json


HEAVY_DASHBOARD_KEYS = {
    "latestFacts",
    "balanceSheet",
    "balanceSheetMetrics",
    "balanceSheetScoringShadow",
    "priceHistory",
}


def trim_dashboard_artifact(path: Path = Path("public/data/dashboard.json")) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    removed: dict[str, int] = {key: 0 for key in sorted(HEAVY_DASHBOARD_KEYS)}
    for row in records:
        if not isinstance(row, dict):
            continue
        for key in HEAVY_DASHBOARD_KEYS:
            if key in row:
                row.pop(key, None)
                removed[key] += 1
    payload["artifactProfile"] = "dashboard-summary"
    write_json(path, payload)
    return {
        "path": str(path),
        "records": len(records),
        "removed": removed,
    }


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("public/data/dashboard.json")
    result = trim_dashboard_artifact(target)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
