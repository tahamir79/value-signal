from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_json import write_json
from scripts.growth_spurt import (
    CONTEXT_WINDOW_SESSIONS,
    DETECTION_THRESHOLDS,
    GROWTH_SPURT_SCHEMA_VERSION,
    PRIMARY_WINDOW_SESSIONS,
    calculate_growth_spurt,
    normalize_price_points,
)
from scripts.providers.price_provider import YahooChartPriceProvider

BENCHMARK_SCHEMA_VERSION = "1.0.0"
DEFAULT_HORIZONS = (21, 30, 63, 90)
SNAPSHOT_FREQUENCY_SESSIONS = 21
FALSE_POSITIVE_RETURN_THRESHOLD = -0.05
FALSE_POSITIVE_DRAWDOWN_THRESHOLD = -0.15


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 8) if values else None


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 8) if values else None


def _percent(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _return_between_price_points(points: list[Any], start_date: str, end_date: str) -> float | None:
    normalized = normalize_price_points(points)
    by_date = {point.date: point.price for point in normalized}
    start = by_date.get(start_date)
    end = by_date.get(end_date)
    if start is None or end is None or start <= 0:
        return None
    return end / start - 1


def _max_adverse_drawdown(prices: list[float], entry: float) -> float | None:
    if not prices or entry <= 0:
        return None
    return min(price / entry - 1 for price in prices if price > 0)


def _load_stock_payloads(stock_dir: Path) -> list[dict[str, Any]]:
    payloads = []
    for path in sorted(stock_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        record = payload.get("record") or {}
        if record.get("priceHistory"):
            payloads.append(record)
    return payloads


def _summarize(observations: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(item["forwardReturn"]) for item in observations if item.get("forwardReturn") is not None]
    excess = [float(item["excessReturnVsSpy"]) for item in observations if item.get("excessReturnVsSpy") is not None]
    drawdowns = [float(item["maxAdverseDrawdown"]) for item in observations if item.get("maxAdverseDrawdown") is not None]
    false_positive_count = sum(1 for item in observations if item.get("isFalsePositive"))
    return {
        "sampleCount": len(observations),
        "positiveForwardPercent": _percent(sum(value > 0 for value in returns), len(returns)),
        "medianForwardReturn": _median(returns),
        "meanForwardReturn": _mean(returns),
        "medianSpyExcessReturn": _median(excess),
        "meanSpyExcessReturn": _mean(excess),
        "medianMaxAdverseDrawdown": _median(drawdowns),
        "meanMaxAdverseDrawdown": _mean(drawdowns),
        "falsePositiveRate": _percent(false_positive_count, len(observations)),
        "falsePositiveCount": false_positive_count,
    }


def _group_summary(observations: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        grouped[str(item.get(key) or "unknown")].append(item)
    return {name: _summarize(rows) for name, rows in sorted(grouped.items())}


def evaluate_growth_spurt_history(
    stock_payloads: Iterable[dict[str, Any]],
    benchmark_prices: Iterable[Any],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    snapshot_frequency_sessions: int = SNAPSHOT_FREQUENCY_SESSIONS,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now()
    benchmark_points = normalize_price_points(benchmark_prices)
    observations: list[dict[str, Any]] = []
    snapshot_status_counts: Counter[str] = Counter()
    candidate_snapshots = 0
    latest_start = max(CONTEXT_WINDOW_SESSIONS, PRIMARY_WINDOW_SESSIONS + 1)
    for payload in stock_payloads:
        security = payload.get("security") or {}
        ticker = str(security.get("ticker") or payload.get("ticker") or "").upper()
        sector = security.get("sector") or "Unknown"
        points = normalize_price_points(payload.get("priceHistory") or [])
        if not ticker or len(points) <= latest_start + max(horizons):
            continue
        for signal_index in range(latest_start, len(points) - max(horizons) - 1, snapshot_frequency_sessions):
            signal_date = points[signal_index].date
            known_prices = points[: signal_index + 1]
            known_benchmark = [point for point in benchmark_points if point.date <= signal_date]
            artifact = calculate_growth_spurt(ticker, known_prices, known_benchmark, generated_at=generated_at)
            candidate_snapshots += 1
            snapshot_status_counts[str(artifact.get("status") or "unavailable")] += 1
            if artifact.get("status") != "detected":
                continue
            entry_index = signal_index + 1
            entry = points[entry_index]
            for horizon in horizons:
                exit_index = entry_index + horizon
                if exit_index >= len(points):
                    continue
                exit_point = points[exit_index]
                forward_return = exit_point.price / entry.price - 1 if entry.price > 0 else None
                spy_return = _return_between_price_points(benchmark_points, entry.date, exit_point.date)
                forward_window_prices = [point.price for point in points[entry_index: exit_index + 1]]
                max_adverse_drawdown = _max_adverse_drawdown(forward_window_prices, entry.price)
                market_regime = "positive_spy" if spy_return is not None and spy_return > 0 else "non_positive_spy"
                is_false_positive = bool(
                    (forward_return is not None and forward_return <= FALSE_POSITIVE_RETURN_THRESHOLD)
                    or (max_adverse_drawdown is not None and max_adverse_drawdown <= FALSE_POSITIVE_DRAWDOWN_THRESHOLD)
                )
                observations.append({
                    "ticker": ticker,
                    "sector": sector,
                    "signalDate": signal_date,
                    "entryDate": entry.date,
                    "exitDate": exit_point.date,
                    "year": signal_date[:4],
                    "horizonSessions": horizon,
                    "growthSpurtScore": artifact.get("growthSpurtScore"),
                    "benchmarkPercentile": artifact.get("benchmarkPercentile"),
                    "forwardReturn": round(forward_return, 8) if forward_return is not None and math.isfinite(forward_return) else None,
                    "spyReturn": round(spy_return, 8) if spy_return is not None and math.isfinite(spy_return) else None,
                    "excessReturnVsSpy": round(forward_return - spy_return, 8) if forward_return is not None and spy_return is not None else None,
                    "maxAdverseDrawdown": round(max_adverse_drawdown, 8) if max_adverse_drawdown is not None else None,
                    "marketRegime": market_regime,
                    "isFalsePositive": is_false_positive,
                    "detectorPriceCount": len(known_prices),
                    "priceHistoryLengthAtTickerEnd": len(points),
                })
    by_horizon = {
        str(horizon): _summarize([item for item in observations if item.get("horizonSessions") == horizon])
        for horizon in horizons
    }
    return {
        "schemaVersion": BENCHMARK_SCHEMA_VERSION,
        "growthSpurtSchemaVersion": GROWTH_SPURT_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "status": "complete" if observations else "insufficient_data",
        "pointInTime": True,
        "benchmark": "SPY",
        "detectorWindowSessions": PRIMARY_WINDOW_SESSIONS,
        "snapshotFrequencySessions": snapshot_frequency_sessions,
        "forwardHorizonsSessions": list(horizons),
        "thresholds": DETECTION_THRESHOLDS,
        "falsePositiveDefinition": {
            "forwardReturnLessThanOrEqual": FALSE_POSITIVE_RETURN_THRESHOLD,
            "maxAdverseDrawdownLessThanOrEqual": FALSE_POSITIVE_DRAWDOWN_THRESHOLD,
        },
        "sampleSize": {
            "candidateSnapshots": candidate_snapshots,
            "detectedSnapshots": snapshot_status_counts.get("detected", 0),
            "forwardObservations": len(observations),
            "uniqueTickersDetected": len({item["ticker"] for item in observations}),
        },
        "snapshotStatusCounts": dict(sorted(snapshot_status_counts.items())),
        "summaryByHorizon": by_horizon,
        "byMarketRegime": _group_summary(observations, "marketRegime"),
        "bySector": _group_summary(observations, "sector"),
        "stabilityByYear": _group_summary(observations, "year"),
        "observationsPreview": observations[:100],
        "holdoutPolicy": {
            "finalHoldoutPeriodUntouched": True,
            "note": "This script reports outcomes under fixed starting thresholds; it does not optimize thresholds against the final period.",
        },
        "limitations": [
            "The benchmark uses the current generated universe, so survivorship bias remains until historical constituents are added.",
            "Forward returns are evaluation statistics for a descriptive tag, not predictions or recommendations.",
            "Provider revisions to historical adjusted prices can change benchmark results.",
        ],
    }


def main() -> int:
    stock_dir = Path("public/data/stocks")
    output = Path("data/reports/growth_spurt_benchmark.json")
    user_agent = os.getenv("VS_USER_AGENT") or "ValueSignal growth spurt benchmark contact@example.invalid"
    try:
        benchmark_prices = YahooChartPriceProvider(user_agent, range_name="5y").fetch("SPY")
    except Exception as exc:
        report = {
            "schemaVersion": BENCHMARK_SCHEMA_VERSION,
            "growthSpurtSchemaVersion": GROWTH_SPURT_SCHEMA_VERSION,
            "generatedAt": _now(),
            "status": "insufficient_data",
            "pointInTime": True,
            "benchmark": "SPY",
            "sampleSize": {"candidateSnapshots": 0, "detectedSnapshots": 0, "forwardObservations": 0, "uniqueTickersDetected": 0},
            "summaryByHorizon": {},
            "byMarketRegime": {},
            "bySector": {},
            "stabilityByYear": {},
            "warnings": [f"SPY benchmark unavailable: {type(exc).__name__}: {exc}"],
        }
        write_json(output, report)
        print(json.dumps({"status": report["status"], "warning": report["warnings"][0]}, indent=2))
        return 0
    report = evaluate_growth_spurt_history(_load_stock_payloads(stock_dir), benchmark_prices)
    write_json(output, report)
    print(json.dumps({"status": report["status"], "sampleSize": report["sampleSize"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
