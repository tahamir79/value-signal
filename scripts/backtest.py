from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from scripts.features import calculate_raw_features, normalize_universe
from scripts.models import FinancialFact, PriceBar
from scripts.scoring import score_universe

BACKTEST_SCHEMA_VERSION = "1.0.0"
DEFAULT_PROTOCOL = {
    "benchmark": "SPY",
    "executionLagSessions": 1,
    "forwardHorizonsSessions": [30, 60, 90],
    "snapshotFrequencySessions": 21,
    "confidenceLevel": 0.95,
    "pointInTimeRule": "Prices and filing availability must be on or before the signal date; entry is the next trading session.",
}


def _price(bar: PriceBar) -> float:
    return bar.adjusted_close if bar.adjusted_close is not None else bar.close


def empty_report(reason: str, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schemaVersion": BACKTEST_SCHEMA_VERSION,
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(),
        "status": "insufficient_data",
        "protocol": DEFAULT_PROTOCOL,
        "snapshotCount": 0,
        "evaluatedObservationCount": 0,
        "observations": [],
        "cohorts": [],
        "biasAudit": {"passed": False, "rejectedForLeakage": 0, "rejectedForDateAlignment": 0, "overlappingWindows": 0, "missingExpectedSymbols": [], "notes": [reason]},
        "traceObservation": None,
        "limitations": [
            "The universe uses today’s ten-company starter list, so survivorship bias remains.",
            "Transaction costs, taxes, slippage, and corporate actions beyond adjusted prices are excluded.",
            "Confidence intervals are descriptive normal intervals and are not proof of economic significance.",
        ],
    }


def build_point_in_time_snapshots(
    price_history: dict[str, list[PriceBar]],
    fact_history: dict[str, list[FinancialFact]],
    signal_dates: list[str],
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for signal_date in signal_dates:
        rows: list[dict[str, Any]] = []
        availability: dict[str, dict[str, str | None]] = {}
        for ticker, full_prices in price_history.items():
            prices = [bar for bar in full_prices if bar.date <= signal_date]
            facts = [fact for fact in fact_history.get(ticker, []) if fact.filed <= signal_date]
            if not prices:
                continue
            rows.append({"ticker": ticker, "asOf": prices[-1].date, "raw": calculate_raw_features(prices, facts)})
            availability[ticker] = {"priceThrough": prices[-1].date, "latestFilingAvailable": max((fact.filed for fact in facts), default=None)}
        if not rows:
            continue
        for scored in score_universe(normalize_universe(rows)):
            source = availability[scored["ticker"]]
            snapshots.append({
                "ticker": scored["ticker"], "signalDate": signal_date, "availableAt": signal_date,
                "sourcePriceThrough": source["priceThrough"], "sourceMaxFiledAt": source["latestFilingAvailable"],
                "signal": scored["signal"], "confidence": scored["confidence"], "scores": scored["scores"],
            })
    return snapshots


def _mean_interval(values: list[float]) -> list[float] | None:
    if not values:
        return None
    mean = statistics.fmean(values)
    if len(values) == 1:
        return [round(mean, 6), round(mean, 6)]
    margin = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return [round(mean - margin, 6), round(mean + margin, 6)]


def _aggregate(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        groups[(item["signal"], item["horizonSessions"], "all")].append(item)
        groups[(item["signal"], item["horizonSessions"], item["marketRegime"])].append(item)
    cohorts = []
    for (signal, horizon, regime), rows in sorted(groups.items()):
        excess = [row["excessReturn"] for row in rows]
        cohorts.append({
            "signal": signal, "horizonSessions": horizon, "marketRegime": regime, "sampleCount": len(rows),
            "meanForwardReturn": round(statistics.fmean(row["forwardReturn"] for row in rows), 6),
            "meanBenchmarkReturn": round(statistics.fmean(row["benchmarkReturn"] for row in rows), 6),
            "meanExcessReturn": round(statistics.fmean(excess), 6),
            "excessReturnConfidenceInterval95": _mean_interval(excess),
            "winRate": round(sum(value > 0 for value in excess) / len(excess), 6),
            "meanAdverseDrawdown": round(statistics.fmean(row["adverseDrawdown"] for row in rows), 6),
        })
    return cohorts


def evaluate_snapshots(
    snapshots: list[dict[str, Any]],
    price_history: dict[str, list[PriceBar]],
    benchmark_prices: list[PriceBar],
    expected_tickers: list[str] | None = None,
    protocol: dict[str, Any] = DEFAULT_PROTOCOL,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    benchmark = {bar.date: _price(bar) for bar in benchmark_prices}
    observations: list[dict[str, Any]] = []
    rejected_leakage = rejected_alignment = 0
    for snapshot in snapshots:
        source_dates = [snapshot.get("availableAt"), snapshot.get("sourcePriceThrough"), snapshot.get("sourceMaxFiledAt")]
        if any(value and value > snapshot["signalDate"] for value in source_dates):
            rejected_leakage += 1
            continue
        bars = sorted(price_history.get(snapshot["ticker"], []), key=lambda bar: bar.date)
        entry_candidates = [index for index, bar in enumerate(bars) if bar.date > snapshot["signalDate"]]
        lag = int(protocol["executionLagSessions"])
        if len(entry_candidates) < lag:
            rejected_alignment += 1
            continue
        entry_index = entry_candidates[lag - 1]
        entry_bar, entry_price = bars[entry_index], _price(bars[entry_index])
        for horizon in protocol["forwardHorizonsSessions"]:
            outcome_index = entry_index + int(horizon)
            if outcome_index >= len(bars):
                continue
            outcome_bar = bars[outcome_index]
            if entry_bar.date not in benchmark or outcome_bar.date not in benchmark or entry_price <= 0 or benchmark[entry_bar.date] <= 0:
                rejected_alignment += 1
                continue
            forward = _price(outcome_bar) / entry_price - 1
            benchmark_return = benchmark[outcome_bar.date] / benchmark[entry_bar.date] - 1
            path = [_price(bar) / entry_price - 1 for bar in bars[entry_index:outcome_index + 1]]
            observations.append({
                "ticker": snapshot["ticker"], "signal": snapshot["signal"], "signalDate": snapshot["signalDate"],
                "availableAt": snapshot.get("availableAt"), "sourcePriceThrough": snapshot.get("sourcePriceThrough"), "sourceMaxFiledAt": snapshot.get("sourceMaxFiledAt"),
                "entryDate": entry_bar.date, "outcomeDate": outcome_bar.date, "horizonSessions": horizon,
                "entryPrice": round(entry_price, 6), "outcomePrice": round(_price(outcome_bar), 6),
                "forwardReturn": round(forward, 6), "benchmarkReturn": round(benchmark_return, 6),
                "excessReturn": round(forward - benchmark_return, 6), "adverseDrawdown": round(min(path), 6),
                "marketRegime": "benchmark_up" if benchmark_return >= 0 else "benchmark_down",
            })
    overlaps = 0
    by_window: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in observations:
        by_window[(item["ticker"], item["horizonSessions"])].append(item)
    for rows in by_window.values():
        ordered = sorted(rows, key=lambda row: row["entryDate"])
        overlaps += sum(current["entryDate"] <= prior["outcomeDate"] for prior, current in zip(ordered, ordered[1:]))
    observed_tickers = set(price_history)
    missing = sorted(set(expected_tickers or []) - observed_tickers)
    if not observations:
        report = empty_report("No snapshots had complete forward and benchmark-aligned outcomes.", generated_at)
        report["snapshotCount"] = len(snapshots)
        report["biasAudit"].update(rejectedForLeakage=rejected_leakage, rejectedForDateAlignment=rejected_alignment, missingExpectedSymbols=missing)
        return report
    return {
        "schemaVersion": BACKTEST_SCHEMA_VERSION, "generatedAt": generated_at, "status": "complete", "protocol": protocol,
        "snapshotCount": len(snapshots), "evaluatedObservationCount": len(observations), "observations": observations, "cohorts": _aggregate(observations),
        "biasAudit": {"passed": rejected_leakage == 0 and not missing, "rejectedForLeakage": rejected_leakage, "rejectedForDateAlignment": rejected_alignment, "overlappingWindows": overlaps, "missingExpectedSymbols": missing, "notes": ["Overlapping windows are disclosed and make observations non-independent."]},
        "traceObservation": observations[0],
        "limitations": [
            "The universe uses today’s ten-company starter list, so survivorship bias remains.",
            "Transaction costs, taxes, slippage, and corporate actions beyond adjusted prices are excluded.",
            "Confidence intervals are descriptive normal intervals and are not proof of economic significance.",
        ],
    }
