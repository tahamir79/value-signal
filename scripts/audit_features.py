from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(data_dir: Path = Path("public/data")) -> list[str]:
    dashboard = load(data_dir / "dashboard.json")
    features = load(data_dir / "features.json")
    by_ticker = {row["ticker"]: row for row in features["records"]}
    failures: list[str] = []

    def load_stock_record(ticker: str) -> dict[str, Any]:
        stock_path = data_dir / "stocks" / f"{ticker}.json"
        if not stock_path.exists():
            raise FileNotFoundError(f"missing stock detail artifact: {stock_path}")
        payload = load(stock_path)
        return payload.get("record", payload)

    unordered, duplicates = [], []
    for row in dashboard["records"]:
        ticker = row["security"]["ticker"]
        stock_record = load_stock_record(ticker)
        dates = [bar["date"] for bar in stock_record["priceHistory"]]
        if dates != sorted(dates):
            unordered.append(ticker)
        if len(dates) != len(set(dates)):
            duplicates.append(ticker)
    if unordered or duplicates:
        failures.append(f"price ordering: unordered={unordered}, duplicates={duplicates}")
    print(f"PRICE ORDERING: {'PASS' if not unordered and not duplicates else 'FAIL'} (ordered={len(dashboard['records']) - len(unordered)}/{len(dashboard['records'])}, duplicate tickers={len(duplicates)})")

    sample = dashboard["records"][0]
    ticker = sample["security"]["ticker"]
    sample_stock = load_stock_record(ticker)
    values = [(bar.get("adjusted_close") or bar["close"]) for bar in sample_stock["priceHistory"][-253:]]
    log_returns = [math.log(current / prior) for prior, current in zip(values, values[1:]) if prior > 0 and current > 0]
    recomputed = statistics.stdev(log_returns) * math.sqrt(252)
    stored = by_ticker[ticker]["raw"]["annualized_volatility"]
    delta = abs(recomputed - stored)
    if delta > 1e-7:
        failures.append(f"annualization mismatch: {ticker} delta={delta}")
    print(f"ANNUALIZATION: {'PASS' if delta <= 1e-7 else 'FAIL'} (factor=sqrt(252)={math.sqrt(252):.8f}, {ticker} delta={delta:.10f})")

    bad_denominators: list[str] = []
    for row in dashboard["records"]:
        ticker = row["security"]["ticker"]
        stock_record = load_stock_record(ticker)
        facts = stock_record["latestFacts"]
        checks = {
            "price": stock_record["priceHistory"][-1].get("adjusted_close") or stock_record["priceHistory"][-1]["close"],
            "shares": facts.get("Shares outstanding", {}).get("value"),
            "assets": facts.get("Assets", {}).get("value"),
        }
        bad_denominators.extend(f"{ticker}:{name}={value}" for name, value in checks.items() if value is not None and value <= 0)
    if bad_denominators:
        failures.append("non-positive denominators: " + ", ".join(bad_denominators))
    print(f"DENOMINATOR SIGNS: {'PASS' if not bad_denominators else 'FAIL'} (non-positive={len(bad_denominators)})")

    print("OUTLIER TRACE (ticker-level raw extrema):")
    for name in features["records"][0]["raw"]:
        values = [(row["raw"][name], row) for row in features["records"] if row["raw"][name] is not None]
        low_value, low = min(values, key=lambda item: item[0])
        high_value, high = max(values, key=lambda item: item[0])
        print(f"  {name}: low={low['ticker']} raw={low_value} winsor={low['winsorized'][name]} pct={low['percentile'][name]}; high={high['ticker']} raw={high_value} winsor={high['winsorized'][name]} pct={high['percentile'][name]}")
    warning_count = sum(len(row["rangeWarnings"]) for row in features["records"])
    print(f"RANGE WARNINGS: {'PASS' if warning_count == 0 else 'REVIEW'} ({warning_count})")
    return failures


if __name__ == "__main__":
    problems = audit()
    raise SystemExit(1 if problems else 0)
