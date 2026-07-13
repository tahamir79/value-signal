from __future__ import annotations

import math
import statistics
from typing import Any

from scripts.models import FinancialFact, PriceBar

FEATURE_SCHEMA_VERSION = "1.0.0"

# Bounds are conservative data-quality controls, not investment assumptions.
FEATURE_SPECS: dict[str, dict[str, Any]] = {
    "return_30d": {"group": "momentum", "valid": (-1.0, 5.0), "winsor": (-0.75, 2.0)},
    "return_90d": {"group": "momentum", "valid": (-1.0, 10.0), "winsor": (-0.85, 3.0)},
    "annualized_volatility": {"group": "risk", "valid": (0.0, 5.0), "winsor": (0.0, 2.0)},
    "max_drawdown_1y": {"group": "risk", "valid": (-1.0, 0.0), "winsor": (-1.0, 0.0)},
    "earnings_yield": {"group": "value", "valid": (-5.0, 5.0), "winsor": (-0.5, 0.5)},
    "sales_yield": {"group": "value", "valid": (0.0, 20.0), "winsor": (0.0, 5.0)},
    "liabilities_to_assets": {"group": "risk", "valid": (0.0, 10.0), "winsor": (0.0, 2.0)},
    "revenue_growth": {"group": "quality", "valid": (-5.0, 10.0), "winsor": (-1.0, 3.0)},
    "net_margin": {"group": "quality", "valid": (-10.0, 10.0), "winsor": (-2.0, 2.0)},
    "net_margin_trend": {"group": "quality", "valid": (-10.0, 10.0), "winsor": (-1.0, 1.0)},
}


def _price(bar: PriceBar) -> float:
    return bar.adjusted_close if bar.adjusted_close is not None else bar.close


def _return(prices: list[PriceBar], sessions: int) -> float | None:
    if len(prices) <= sessions:
        return None
    start, end = _price(prices[-sessions - 1]), _price(prices[-1])
    return end / start - 1 if start > 0 else None


def _volatility(prices: list[PriceBar]) -> float | None:
    values = [_price(bar) for bar in prices[-253:]]
    log_returns = [math.log(current / prior) for prior, current in zip(values, values[1:]) if prior > 0 and current > 0]
    return statistics.stdev(log_returns) * math.sqrt(252) if len(log_returns) >= 30 else None


def _drawdown(prices: list[PriceBar]) -> float | None:
    values = [_price(bar) for bar in prices[-252:]]
    if not values:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return worst


def _annual_series(facts: list[FinancialFact], label: str) -> list[FinancialFact]:
    by_period: dict[str, FinancialFact] = {}
    for fact in facts:
        if fact.label != label or fact.form != "10-K" or fact.fiscal_period != "FY":
            continue
        prior = by_period.get(fact.period_end)
        if prior is None or fact.filed > prior.filed:
            by_period[fact.period_end] = fact
    return sorted(by_period.values(), key=lambda fact: (fact.period_end, fact.filed))


def _latest(facts: list[FinancialFact], label: str) -> FinancialFact | None:
    matches = [fact for fact in facts if fact.label == label]
    return max(matches, key=lambda fact: (fact.period_end, fact.filed), default=None)


def derive_fields(prices: list[PriceBar], facts: dict[str, FinancialFact]) -> dict[str, float | None]:
    latest = prices[-1]
    prior = prices[-2] if len(prices) > 1 else None
    change = ((latest.close / prior.close) - 1) * 100 if prior and prior.close else None
    shares, assets, liabilities = facts.get("Shares outstanding"), facts.get("Assets"), facts.get("Liabilities")
    revenue, income, gross_profit = facts.get("Revenue"), facts.get("Net income"), facts.get("Gross profit")
    return {
        "latestPrice": round(latest.close, 4),
        "dailyChangePercent": round(change, 4) if change is not None else None,
        "marketCapBillions": round(latest.close * shares.value / 1_000_000_000, 4) if shares else None,
        "liabilitiesToAssets": round(liabilities.value / assets.value, 6) if assets and liabilities and assets.value else None,
        "latestRevenueBillions": round(revenue.value / 1_000_000_000, 4) if revenue else None,
        "grossMarginPercent": round(gross_profit.value / revenue.value * 100, 4) if gross_profit and revenue and revenue.value else None,
        "netMarginPercent": round(income.value / revenue.value * 100, 4) if income and revenue and revenue.value else None,
    }


def calculate_raw_features(prices: list[PriceBar], facts: list[FinancialFact]) -> dict[str, float | None]:
    prices = sorted(prices, key=lambda bar: bar.date)
    revenue, income = _annual_series(facts, "Revenue"), _annual_series(facts, "Net income")
    gross_profit = _annual_series(facts, "Gross profit")
    latest_revenue = revenue[-1].value if revenue else None
    latest_income = income[-1].value if income else None
    latest_gross_profit = gross_profit[-1].value if gross_profit else None
    previous_revenue = revenue[-2].value if len(revenue) > 1 else None
    previous_income = income[-2].value if len(income) > 1 else None
    shares, assets, liabilities = _latest(facts, "Shares outstanding"), _latest(facts, "Assets"), _latest(facts, "Liabilities")
    market_cap = _price(prices[-1]) * shares.value if prices and shares else None
    current_margin = latest_income / latest_revenue if latest_income is not None and latest_revenue else None
    previous_margin = previous_income / previous_revenue if previous_income is not None and previous_revenue else None
    raw = {
        "return_30d": _return(prices, 30),
        "return_90d": _return(prices, 90),
        "annualized_volatility": _volatility(prices),
        "max_drawdown_1y": _drawdown(prices),
        "earnings_yield": latest_income / market_cap if latest_income is not None and market_cap else None,
        "sales_yield": latest_revenue / market_cap if latest_revenue is not None and market_cap else None,
        "liabilities_to_assets": liabilities.value / assets.value if assets and liabilities and assets.value else None,
        "revenue_growth": latest_revenue / previous_revenue - 1 if latest_revenue is not None and previous_revenue else None,
        "net_margin": current_margin,
        "net_margin_trend": current_margin - previous_margin if current_margin is not None and previous_margin is not None else None,
        "gross_margin": latest_gross_profit / latest_revenue if latest_gross_profit is not None and latest_revenue else None,
        "latest_revenue": latest_revenue,
        "gross_profit": latest_gross_profit,
    }
    return {name: round(value, 8) if value is not None and math.isfinite(value) else None for name, value in raw.items()}


def _percentile(values: list[float], value: float) -> float:
    if len(values) == 1:
        return 0.5
    below = sum(candidate < value for candidate in values)
    equal = sum(candidate == value for candidate in values)
    return (below + (equal - 1) / 2) / (len(values) - 1)


def normalize_universe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        row["winsorized"] = {}
        row["percentile"] = {}
        row["missing"] = {name: row["raw"].get(name) is None for name in FEATURE_SPECS}
        row["rangeWarnings"] = []
    for name, spec in FEATURE_SPECS.items():
        low, high = spec["winsor"]
        for row in rows:
            value = row["raw"].get(name)
            if value is None:
                row["winsorized"][name] = None
                row["percentile"][name] = None
                continue
            valid_low, valid_high = spec["valid"]
            if not valid_low <= value <= valid_high:
                row["rangeWarnings"].append(name)
            row["winsorized"][name] = round(min(max(value, low), high), 8)
        universe = sorted(row["winsorized"][name] for row in rows if row["winsorized"][name] is not None)
        for row in rows:
            value = row["winsorized"][name]
            row["percentile"][name] = round(_percentile(universe, value), 6) if value is not None else None
    return rows
