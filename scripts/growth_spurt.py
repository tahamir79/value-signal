from __future__ import annotations

import math
import os
import statistics
from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

GROWTH_SPURT_SCHEMA_VERSION = "1.0.0"
PRIMARY_WINDOW_SESSIONS = 63
CONFIRMATION_WINDOW_SESSIONS = 21
CONTEXT_WINDOW_SESSIONS = 126
MIN_PRIMARY_OBSERVATIONS = 50
TRADING_SESSIONS_PER_YEAR = 252

GROWTH_SPURT_MODE_VALUES = {"off", "shadow", "display", "official"}
SCORE_WEIGHTS = {
    "directionScore": 0.30,
    "consistencyScore": 0.25,
    "relativeStrengthScore": 0.20,
    "drawdownControlScore": 0.15,
    "confirmationScore": 0.10,
}
DETECTION_THRESHOLDS = {
    "detectedScore": 70.0,
    "emergingScore": 55.0,
    "trendFitR2_63d": 0.45,
    "positiveWeekRatio63d": 0.60,
    "maxDrawdown63d": -0.15,
    "spikeDominance": 0.35,
    "spikeGainShare": 0.65,
}


@dataclass(frozen=True)
class PricePoint:
    date: str
    price: float


def growth_spurt_mode(value: str | None = None) -> str:
    mode = (value or os.getenv("GROWTH_SPURT_MODE") or "display").strip().lower()
    return mode if mode in GROWTH_SPURT_MODE_VALUES else "display"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _round(value: float | None, digits: int = 8) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return min(max(value, low), high)


def _weighted(values: Iterable[tuple[float | None, float]]) -> float | None:
    total = 0.0
    weight = 0.0
    for value, item_weight in values:
        if value is None or not math.isfinite(value):
            continue
        total += value * item_weight
        weight += item_weight
    return _round(total / weight, 4) if weight else None


def _score_positive(value: float | None, target: float) -> float | None:
    if value is None:
        return None
    return _clamp((value / target) * 100.0) if target > 0 else None


def _score_symmetric(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    if high <= low:
        return None
    return _clamp(((value - low) / (high - low)) * 100.0)


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _price(row: Any) -> float | None:
    value = _field(row, "adjusted_close")
    if value is None:
        value = _field(row, "close")
    if value is None:
        value = _field(row, "price")
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 0 else None


def normalize_price_points(prices: Iterable[Any]) -> list[PricePoint]:
    by_date: dict[str, PricePoint] = {}
    rows = sorted(prices, key=lambda row: str(_field(row, "date") or ""))
    for row in rows:
        date = str(_field(row, "date") or "").strip()
        price = _price(row)
        if not date or price is None:
            continue
        by_date[date] = PricePoint(date, price)
    return list(by_date.values())


def _window(points: list[PricePoint], observations: int) -> list[PricePoint]:
    return points[-observations:] if len(points) > observations else points[:]


def _simple_return(points: list[PricePoint], sessions: int) -> float | None:
    if len(points) <= sessions:
        return None
    start = points[-sessions - 1].price
    end = points[-1].price
    return end / start - 1 if start > 0 else None


def _return_between(points: list[PricePoint], start_date: str, end_date: str) -> float | None:
    dates = [point.date for point in points]
    start_index = bisect_right(dates, start_date) - 1
    end_index = bisect_right(dates, end_date) - 1
    if start_index < 0 or end_index < 0 or end_index <= start_index:
        return None
    start = points[start_index].price
    end = points[end_index].price
    return end / start - 1 if start > 0 else None


def _daily_returns(values: list[float]) -> list[float]:
    return [current / prior - 1 for prior, current in zip(values, values[1:]) if prior > 0 and current > 0]


def _log_returns(values: list[float]) -> list[float]:
    return [math.log(current / prior) for prior, current in zip(values, values[1:]) if prior > 0 and current > 0]


def _theil_sen(log_prices: list[float]) -> dict[str, float]:
    if len(log_prices) < 2:
        return {"slope": 0.0, "intercept": log_prices[0] if log_prices else 0.0, "r2": 0.0, "residualVolatility": 0.0}
    slopes = [
        (log_prices[j] - log_prices[i]) / (j - i)
        for i in range(len(log_prices) - 1)
        for j in range(i + 1, len(log_prices))
    ]
    slope = statistics.median(slopes)
    intercept = statistics.median(log_prices[index] - slope * index for index in range(len(log_prices)))
    fitted = [intercept + slope * index for index in range(len(log_prices))]
    residuals = [actual - expected for actual, expected in zip(log_prices, fitted)]
    residual_sum = sum(value * value for value in residuals)
    mean = statistics.fmean(log_prices)
    total_sum = sum((value - mean) ** 2 for value in log_prices)
    if total_sum == 0:
        r2 = 1.0 if residual_sum == 0 else 0.0
    else:
        r2 = _clamp(1.0 - residual_sum / total_sum, 0.0, 1.0)
    residual_volatility = statistics.stdev(residuals) if len(residuals) > 1 else 0.0
    return {"slope": slope, "intercept": intercept, "r2": r2, "residualVolatility": residual_volatility}


def _trend(points: list[PricePoint]) -> dict[str, Any]:
    values = [point.price for point in points]
    log_prices = [math.log(value) for value in values]
    fit = _theil_sen(log_prices)
    fitted = [fit["intercept"] + fit["slope"] * index for index in range(len(log_prices))]
    percent_above = sum(actual >= expected for actual, expected in zip(log_prices, fitted)) / len(log_prices) if log_prices else None
    return {
        "slope": fit["slope"],
        "annualizedReturn": math.exp(fit["slope"] * TRADING_SESSIONS_PER_YEAR) - 1,
        "r2": fit["r2"],
        "residualVolatility": fit["residualVolatility"],
        "percentAboveTrendLine": percent_above,
    }


def _positive_week_ratio(points: list[PricePoint]) -> float | None:
    values = [point.price for point in points]
    week_returns = []
    for start in range(0, len(values) - 5, 5):
        prior = values[start]
        current = values[start + 5]
        if prior > 0 and current > 0:
            week_returns.append(current / prior - 1)
    if not week_returns:
        return None
    return sum(value > 0 for value in week_returns) / len(week_returns)


def _max_drawdown(points: list[PricePoint]) -> float | None:
    if not points:
        return None
    peak = points[0].price
    worst = 0.0
    for point in points:
        peak = max(peak, point.price)
        if peak > 0:
            worst = min(worst, point.price / peak - 1)
    return worst


def _downside_volatility(points: list[PricePoint]) -> float | None:
    downside = [value for value in _log_returns([point.price for point in points]) if value < 0]
    if not downside:
        return 0.0 if len(points) > 1 else None
    return statistics.stdev(downside) if len(downside) > 1 else 0.0


def _largest_one_day_contribution(points: list[PricePoint]) -> tuple[float | None, float | None]:
    returns = _daily_returns([point.price for point in points])
    if not returns:
        return None, None
    total_abs = sum(abs(value) for value in returns)
    contribution = max(abs(value) for value in returns) / total_abs if total_abs else None
    total_return = points[-1].price / points[0].price - 1 if points[0].price else None
    largest_positive = max([value for value in returns if value > 0], default=0.0)
    gain_share = largest_positive / total_return if total_return and total_return > 0 else None
    return contribution, gain_share


def _status(
    *,
    score: float | None,
    metrics: dict[str, float | None],
    warnings: list[str],
) -> str:
    def value(name: str, default: float) -> float:
        candidate = metrics.get(name)
        return candidate if candidate is not None else default

    if score is None:
        return "unavailable"
    spike_dominated = "ONE_DAY_SPIKE_DOMINATED" in warnings
    detected = (
        score >= DETECTION_THRESHOLDS["detectedScore"]
        and value("trendSlope63d", 0.0) > 0
        and value("return63d", -1.0) > 0
        and value("return21d", -1.0) >= 0
        and value("trendFitR2_63d", 0.0) >= DETECTION_THRESHOLDS["trendFitR2_63d"]
        and value("positiveWeekRatio63d", 0.0) >= DETECTION_THRESHOLDS["positiveWeekRatio63d"]
        and value("maxDrawdown63d", -1.0) >= DETECTION_THRESHOLDS["maxDrawdown63d"]
        and not spike_dominated
    )
    if detected:
        return "detected"
    emerging = (
        score >= DETECTION_THRESHOLDS["emergingScore"]
        and value("trendSlope63d", 0.0) > 0
        and value("return63d", -1.0) > 0
        and not spike_dominated
    )
    return "emerging" if emerging else "not_detected"


def _reason_codes(status: str, metrics: dict[str, float | None], score_breakdown: dict[str, float | None], warnings: list[str]) -> list[str]:
    def value(source: dict[str, float | None], name: str, default: float) -> float:
        candidate = source.get(name)
        return candidate if candidate is not None else default

    codes: list[str] = []
    if status == "detected":
        codes.append("GROWTH_SPURT_DETECTED")
    elif status == "emerging":
        codes.append("GROWTH_SPURT_EMERGING")
    elif status == "unavailable":
        codes.append("TREND_HISTORY_INSUFFICIENT")
    if value(metrics, "trendSlope63d", 0.0) > 0 and value(metrics, "trendAnnualizedReturn63d", 0.0) > 0.20:
        codes.append("TREND_SLOPE_STRONG")
    if value(metrics, "trendFitR2_63d", 0.0) >= DETECTION_THRESHOLDS["trendFitR2_63d"] and value(metrics, "positiveWeekRatio63d", 0.0) >= DETECTION_THRESHOLDS["positiveWeekRatio63d"]:
        codes.append("TREND_CONSISTENCY_STRONG")
    if value(score_breakdown, "relativeStrengthScore", 0.0) >= 60:
        codes.append("MARKET_RELATIVE_STRENGTH")
    elif score_breakdown.get("relativeStrengthScore") is not None:
        codes.append("TREND_WEAK_RELATIVE_TO_MARKET")
    if metrics.get("maxDrawdown63d") is not None and metrics["maxDrawdown63d"] >= -0.08:
        codes.append("LOW_TREND_DRAWDOWN")
    if value(metrics, "return21d", -1.0) >= 0 and value(metrics, "trendSlope21d", -1.0) > 0:
        codes.append("RECENT_TREND_CONFIRMED")
    if value(score_breakdown, "consistencyScore", 100.0) < 45:
        codes.append("TREND_TOO_VOLATILE")
    if "ONE_DAY_SPIKE_DOMINATED" in warnings:
        codes.append("ONE_DAY_SPIKE_DOMINATED")
    return list(dict.fromkeys(codes))


def unavailable_growth_spurt_artifact(ticker: str, generated_at: str | None = None, reason: str = "TREND_HISTORY_INSUFFICIENT") -> dict[str, Any]:
    return {
        "schemaVersion": GROWTH_SPURT_SCHEMA_VERSION,
        "ticker": ticker.upper(),
        "generatedAt": generated_at or _now(),
        "marketDataAsOf": None,
        "status": "unavailable",
        "growthSpurtScore": None,
        "primaryWindowSessions": PRIMARY_WINDOW_SESSIONS,
        "confirmationWindowSessions": CONFIRMATION_WINDOW_SESSIONS,
        "metrics": {
            "return21d": None,
            "return63d": None,
            "trendSlope21d": None,
            "trendSlope63d": None,
            "trendAnnualizedReturn63d": None,
            "trendFitR2_63d": None,
            "positiveWeekRatio63d": None,
            "trendResidualVolatility63d": None,
            "maxDrawdown63d": None,
            "downsideVolatility63d": None,
            "excessReturnVsSpy21d": None,
            "excessReturnVsSpy63d": None,
            "trendAcceleration": None,
            "largestOneDayContribution63d": None,
            "percentAboveTrendLine63d": None,
        },
        "scoreBreakdown": {
            "directionScore": None,
            "consistencyScore": None,
            "relativeStrengthScore": None,
            "drawdownControlScore": None,
            "confirmationScore": None,
        },
        "benchmarkPercentile": None,
        "metricPercentiles": {},
        "reasonCodes": ["TREND_HISTORY_INSUFFICIENT"],
        "warnings": [reason],
    }


def calculate_growth_spurt(
    ticker: str,
    prices: Iterable[Any],
    benchmark_prices: Iterable[Any] | None,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _now()
    points = normalize_price_points(prices)
    benchmark_points = normalize_price_points(benchmark_prices or [])
    if len(points) < MIN_PRIMARY_OBSERVATIONS:
        return unavailable_growth_spurt_artifact(ticker, generated_at, "TREND_HISTORY_INSUFFICIENT")
    if len(benchmark_points) < MIN_PRIMARY_OBSERVATIONS:
        return unavailable_growth_spurt_artifact(ticker, generated_at, "SPY_BENCHMARK_UNAVAILABLE")

    primary = _window(points, PRIMARY_WINDOW_SESSIONS)
    confirmation = _window(points, CONFIRMATION_WINDOW_SESSIONS)
    previous = points[-(PRIMARY_WINDOW_SESSIONS + CONFIRMATION_WINDOW_SESSIONS):-CONFIRMATION_WINDOW_SESSIONS]
    previous_42 = previous[-42:] if previous else []
    trend63 = _trend(primary)
    trend21 = _trend(confirmation) if len(confirmation) >= 2 else {"slope": None}
    trend_prev = _trend(previous_42) if len(previous_42) >= 2 else {"slope": None}
    start21 = points[-CONFIRMATION_WINDOW_SESSIONS - 1].date if len(points) > CONFIRMATION_WINDOW_SESSIONS else confirmation[0].date
    start63 = points[-PRIMARY_WINDOW_SESSIONS - 1].date if len(points) > PRIMARY_WINDOW_SESSIONS else primary[0].date
    end_date = points[-1].date
    return21 = _simple_return(points, CONFIRMATION_WINDOW_SESSIONS)
    return63 = _simple_return(points, PRIMARY_WINDOW_SESSIONS)
    spy21 = _return_between(benchmark_points, start21, end_date)
    spy63 = _return_between(benchmark_points, start63, end_date)
    max_drawdown = _max_drawdown(primary)
    largest_contribution, largest_gain_share = _largest_one_day_contribution(primary)
    warnings: list[str] = []
    if largest_contribution is not None and largest_contribution >= DETECTION_THRESHOLDS["spikeDominance"]:
        warnings.append("ONE_DAY_SPIKE_DOMINATED")
    if largest_gain_share is not None and largest_gain_share >= DETECTION_THRESHOLDS["spikeGainShare"]:
        warnings.append("ONE_DAY_SPIKE_DOMINATED")
    if spy21 is None or spy63 is None:
        warnings.append("SPY_BENCHMARK_ALIGNMENT_UNAVAILABLE")

    metrics = {
        "return21d": _round(return21),
        "return63d": _round(return63),
        "trendSlope21d": _round(trend21.get("slope")),
        "trendSlope63d": _round(trend63.get("slope")),
        "trendAnnualizedReturn63d": _round(trend63.get("annualizedReturn")),
        "trendFitR2_63d": _round(trend63.get("r2")),
        "positiveWeekRatio63d": _round(_positive_week_ratio(primary)),
        "trendResidualVolatility63d": _round(trend63.get("residualVolatility")),
        "maxDrawdown63d": _round(max_drawdown),
        "downsideVolatility63d": _round(_downside_volatility(primary)),
        "excessReturnVsSpy21d": _round(return21 - spy21 if return21 is not None and spy21 is not None else None),
        "excessReturnVsSpy63d": _round(return63 - spy63 if return63 is not None and spy63 is not None else None),
        "trendAcceleration": _round(trend21.get("slope") - trend_prev.get("slope") if trend21.get("slope") is not None and trend_prev.get("slope") is not None else None),
        "largestOneDayContribution63d": _round(largest_contribution),
        "percentAboveTrendLine63d": _round(trend63.get("percentAboveTrendLine")),
    }
    direction = _weighted([
        (_score_positive(metrics["trendAnnualizedReturn63d"], 0.35), 0.45),
        (_score_positive(metrics["return63d"], 0.12), 0.35),
        (_score_positive(metrics["return21d"], 0.03), 0.20),
    ])
    consistency = _weighted([
        (_score_symmetric(metrics["trendFitR2_63d"], 0.25, 0.75), 0.35),
        (_score_symmetric(metrics["positiveWeekRatio63d"], 0.45, 0.80), 0.30),
        (_score_symmetric(metrics["percentAboveTrendLine63d"], 0.45, 0.75), 0.15),
        (_clamp(100.0 * (1.0 - (metrics["trendResidualVolatility63d"] or 0.0) / 0.055)) if metrics["trendResidualVolatility63d"] is not None else None, 0.20),
    ])
    relative = _weighted([
        (_score_symmetric(metrics["excessReturnVsSpy63d"], -0.08, 0.08), 0.65),
        (_score_symmetric(metrics["excessReturnVsSpy21d"], -0.04, 0.04), 0.35),
    ])
    drawdown_control = _clamp(100.0 * (1.0 - abs(max_drawdown or 0.0) / 0.30)) if max_drawdown is not None else None
    confirmation_score = _weighted([
        (_score_positive(metrics["return21d"], 0.03), 0.40),
        (_score_positive(metrics["trendSlope21d"], 0.001), 0.40),
        (_score_symmetric(metrics["trendAcceleration"], -0.001, 0.001), 0.20),
    ])
    score_breakdown = {
        "directionScore": _round(direction, 4),
        "consistencyScore": _round(consistency, 4),
        "relativeStrengthScore": _round(relative, 4),
        "drawdownControlScore": _round(drawdown_control, 4),
        "confirmationScore": _round(confirmation_score, 4),
    }
    total_score = _weighted((score_breakdown[name], weight) for name, weight in SCORE_WEIGHTS.items())
    if "ONE_DAY_SPIKE_DOMINATED" in warnings and total_score is not None:
        total_score = min(total_score, DETECTION_THRESHOLDS["emergingScore"] - 1)
    status = _status(score=total_score, metrics=metrics, warnings=warnings)
    reason_codes = _reason_codes(status, metrics, score_breakdown, warnings)
    return {
        "schemaVersion": GROWTH_SPURT_SCHEMA_VERSION,
        "ticker": ticker.upper(),
        "generatedAt": generated_at,
        "marketDataAsOf": end_date,
        "status": status,
        "growthSpurtScore": _round(total_score, 2),
        "primaryWindowSessions": PRIMARY_WINDOW_SESSIONS,
        "confirmationWindowSessions": CONFIRMATION_WINDOW_SESSIONS,
        "metrics": metrics,
        "scoreBreakdown": score_breakdown,
        "benchmarkPercentile": None,
        "metricPercentiles": {},
        "reasonCodes": reason_codes,
        "warnings": list(dict.fromkeys(warnings)),
    }


def _percentile(values: list[float], value: float) -> float:
    if len(values) == 1:
        return 0.5
    below = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    return (below + (equal - 1) / 2) / (len(values) - 1)


def apply_growth_spurt_percentiles(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [artifact for artifact in artifacts if artifact.get("growthSpurtScore") is not None]
    fields = {
        "trendSlope63d": lambda item: (item.get("metrics") or {}).get("trendSlope63d"),
        "trendFitR2_63d": lambda item: (item.get("metrics") or {}).get("trendFitR2_63d"),
        "excessReturnVsSpy63d": lambda item: (item.get("metrics") or {}).get("excessReturnVsSpy63d"),
        "drawdownControlScore": lambda item: (item.get("scoreBreakdown") or {}).get("drawdownControlScore"),
        "growthSpurtScore": lambda item: item.get("growthSpurtScore"),
    }
    universes: dict[str, list[float]] = {}
    for name, getter in fields.items():
        universes[name] = sorted(float(value) for item in candidates if (value := getter(item)) is not None)
    for artifact in artifacts:
        percentiles: dict[str, float | None] = {}
        for name, getter in fields.items():
            value = getter(artifact)
            universe = universes[name]
            percentiles[name] = round(_percentile(universe, float(value)), 6) if value is not None and universe else None
        artifact["metricPercentiles"] = percentiles
        artifact["benchmarkPercentile"] = percentiles.get("growthSpurtScore")
    return artifacts


def growth_spurt_counts(artifacts: Iterable[dict[str, Any]], failures: int = 0, mode: str | None = None) -> dict[str, int | str]:
    counts = {"detected": 0, "emerging": 0, "not_detected": 0, "unavailable": 0}
    attempted = 0
    for artifact in artifacts:
        attempted += 1
        status = str(artifact.get("status") or "unavailable")
        if status in counts:
            counts[status] += 1
        else:
            counts["unavailable"] += 1
    return {
        "growthSpurtMode": growth_spurt_mode(mode),
        "stocksGrowthSpurtAttempted": attempted,
        "stocksGrowthSpurtDetected": counts["detected"],
        "stocksGrowthSpurtEmerging": counts["emerging"],
        "stocksGrowthSpurtNotDetected": counts["not_detected"],
        "stocksGrowthSpurtUnavailable": counts["unavailable"],
        "growthSpurtCalculationFailures": failures,
    }
