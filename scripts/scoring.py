from __future__ import annotations

from copy import deepcopy
from typing import Any

SCORE_SCHEMA_VERSION = "1.0.0"
WEIGHTS: dict[str, dict[str, float]] = {
    "value": {"earnings_yield": 0.60, "sales_yield": 0.40},
    "quality": {"net_margin": 0.45, "revenue_growth": 0.30, "net_margin_trend": 0.25},
    "momentum": {"return_90d": 0.60, "return_30d": 0.40},
    "marketRisk": {"max_drawdown_1y": 0.55, "annualized_volatility": 0.45},
    "balanceSheetRisk": {"liabilities_to_assets": 1.0},
}
INVERTED = {"max_drawdown_1y"}

EXPLANATIONS = {
    "VALUE_STRONG": "Valuation features rank strongly within the current research universe.",
    "VALUE_WEAK": "Valuation evidence ranks below most companies in the current universe.",
    "QUALITY_STRONG": "Profitability and growth evidence rank strongly within the current universe.",
    "QUALITY_WEAK": "Quality evidence is comparatively weak or deteriorating.",
    "MOMENTUM_RISK_HIGH": "Recent price performance is weak relative to the research universe.",
    "MARKET_RISK_HIGH": "Volatility or drawdown evidence indicates elevated market risk.",
    "BALANCE_SHEET_RISK_HIGH": "Leverage evidence ranks among the riskiest records in the universe.",
    "EVIDENCE_SPARSE": "Too many required features are missing for a responsible classification.",
    "EVIDENCE_PARTIAL": "Some inputs are missing, so the classification carries reduced confidence.",
    "EVIDENCE_COMPLETE": "Nearly all required feature inputs are available.",
}


def _bounded(value: float) -> float:
    return round(min(100.0, max(0.0, value)), 4)


def component_score(percentiles: dict[str, float | None], weights: dict[str, float], inverted: set[str] = INVERTED) -> dict[str, Any]:
    available = {name: weight for name, weight in weights.items() if percentiles.get(name) is not None}
    total_weight = sum(available.values())
    if not total_weight:
        return {"score": None, "coverage": 0.0, "contributions": []}
    contributions = []
    score = 0.0
    for name, weight in available.items():
        percentile = min(1.0, max(0.0, float(percentiles[name])))
        directed = 1 - percentile if name in inverted else percentile
        normalized_weight = weight / total_weight
        contribution = directed * normalized_weight * 100
        score += contribution
        contributions.append({"feature": name, "percentile": round(percentile, 6), "directedPercentile": round(directed, 6), "weight": round(normalized_weight, 6), "points": round(contribution, 4)})
    return {"score": _bounded(score), "coverage": round(total_weight / sum(weights.values()), 4), "contributions": contributions}


def confidence_for(raw: dict[str, float | None]) -> tuple[str, int]:
    available = sum(raw.get(name) is not None for name in {feature for weights in WEIGHTS.values() for feature in weights})
    if available >= 9:
        return "High", available
    if available >= 7:
        return "Medium", available
    if available >= 5:
        return "Low", available
    return "Insufficient", available


def classify(scores: dict[str, float | None], confidence: str) -> str:
    if confidence == "Insufficient":
        return "insufficient-evidence"
    value = scores.get("value")
    quality = scores.get("quality")
    momentum_risk = scores.get("momentumRisk")
    market_risk = scores.get("marketRisk")
    balance_risk = scores.get("balanceSheetRisk")
    if value is not None and value >= 65 and balance_risk is not None and balance_risk >= 70:
        return "value-trap-risk"
    if momentum_risk is not None and momentum_risk >= 70:
        return "momentum-risk"
    if value is not None and quality is not None and value >= 70 and quality >= 50 and (market_risk is None or market_risk < 70) and (balance_risk is None or balance_risk < 70):
        return "potentially-undervalued"
    if quality is not None and quality >= 70 and (balance_risk is None or balance_risk < 70):
        return "quality-watchlist"
    return "neutral"


def reason_codes(scores: dict[str, float | None], confidence: str) -> list[str]:
    codes: list[str] = []
    if confidence == "Insufficient":
        codes.append("EVIDENCE_SPARSE")
    elif confidence in {"Low", "Medium"}:
        codes.append("EVIDENCE_PARTIAL")
    else:
        codes.append("EVIDENCE_COMPLETE")
    if scores.get("value") is not None:
        if scores["value"] >= 70: codes.append("VALUE_STRONG")
        elif scores["value"] <= 30: codes.append("VALUE_WEAK")
    if scores.get("quality") is not None:
        if scores["quality"] >= 70: codes.append("QUALITY_STRONG")
        elif scores["quality"] <= 30: codes.append("QUALITY_WEAK")
    if scores.get("momentumRisk") is not None and scores["momentumRisk"] >= 70: codes.append("MOMENTUM_RISK_HIGH")
    if scores.get("marketRisk") is not None and scores["marketRisk"] >= 70: codes.append("MARKET_RISK_HIGH")
    if scores.get("balanceSheetRisk") is not None and scores["balanceSheetRisk"] >= 70: codes.append("BALANCE_SHEET_RISK_HIGH")
    return codes


def score_record(feature_row: dict[str, Any], weights: dict[str, dict[str, float]] = WEIGHTS) -> dict[str, Any]:
    components = {name: component_score(feature_row["percentile"], component_weights) for name, component_weights in weights.items()}
    scores = {name: result["score"] for name, result in components.items()}
    scores["momentumRisk"] = _bounded(100 - scores["momentum"]) if scores["momentum"] is not None else None
    confidence, available = confidence_for(feature_row["raw"])
    label = classify(scores, confidence)
    codes = reason_codes(scores, confidence)
    return {"ticker": feature_row["ticker"], "asOf": feature_row["asOf"], "scoreVersion": SCORE_SCHEMA_VERSION, "signal": label, "confidence": confidence, "availableFeatures": available, "totalFeatures": 10, "scores": scores, "components": components, "reasonCodes": codes, "explanations": [EXPLANATIONS[code] for code in codes]}


def score_universe(feature_rows: list[dict[str, Any]], weights: dict[str, dict[str, float]] = WEIGHTS) -> list[dict[str, Any]]:
    return [score_record(row, weights) for row in feature_rows]


def sensitivity_scenarios(feature_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    baseline = {row["ticker"]: score_record(row) for row in feature_rows}
    scenarios = []
    for component, component_weights in WEIGHTS.items():
        for feature in component_weights:
            for multiplier in (0.8, 1.2):
                varied = deepcopy(WEIGHTS)
                varied[component][feature] *= multiplier
                results = {row["ticker"]: score_record(row, varied) for row in feature_rows}
                changed = [ticker for ticker in baseline if baseline[ticker]["signal"] != results[ticker]["signal"]]
                scenarios.append({"component": component, "feature": feature, "multiplier": multiplier, "changedLabels": changed, "changedCount": len(changed)})
    return scenarios
