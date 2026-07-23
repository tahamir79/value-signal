from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.artifact_paths import ticker_artifact_path, ticker_artifact_stem


PUBLIC_DATA = Path("public/data")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repair_directory(directory: Path, tickers: list[str]) -> list[dict[str, str]]:
    repaired: list[dict[str, str]] = []
    for ticker in tickers:
        safe_path = ticker_artifact_path(directory, ticker)
        raw_path = directory / f"{ticker.upper()}.json"
        if raw_path == safe_path or not raw_path.exists():
            continue
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.replace(safe_path)
        repaired.append({"ticker": ticker.upper(), "from": str(raw_path), "to": str(safe_path)})
    return repaired


def repair_reserved_artifact_names(data_dir: Path = PUBLIC_DATA) -> dict[str, Any]:
    stocks_summary = _load(data_dir / "stocks" / "summary.json")
    forecasts_summary = _load(data_dir / "forecasts" / "summary.json")
    stock_tickers = [
        str(row.get("ticker", "")).upper()
        for row in stocks_summary.get("records", [])
        if isinstance(row, dict) and ticker_artifact_stem(str(row.get("ticker", ""))).startswith("_")
    ]
    forecast_tickers = [
        str(row.get("ticker", "")).upper()
        for row in forecasts_summary.get("forecasts", [])
        if isinstance(row, dict) and ticker_artifact_stem(str(row.get("ticker", ""))).startswith("_")
    ]
    return {
        "stocks": _repair_directory(data_dir / "stocks", stock_tickers),
        "forecasts": _repair_directory(data_dir / "forecasts", forecast_tickers),
    }


def main() -> int:
    result = repair_reserved_artifact_names(Path(sys.argv[1]) if len(sys.argv) > 1 else PUBLIC_DATA)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
