from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.models import FinancialFact, Security

BALANCE_SHEET_SCHEMA_VERSION = "1.0.0"
TARGETS_PATH = Path("data/scoring/balance_sheet_targets.json")

FIELDS: dict[str, str] = {
    "assets": "Assets",
    "currentAssets": "Current assets",
    "cashAndEquivalents": "Cash and equivalents",
    "shortTermInvestments": "Short-term investments",
    "accountsReceivable": "Accounts receivable",
    "inventory": "Inventory",
    "propertyPlantEquipmentNet": "Property plant and equipment, net",
    "goodwill": "Goodwill",
    "intangibleAssets": "Intangible assets",
    "liabilities": "Liabilities",
    "currentLiabilities": "Current liabilities",
    "accountsPayable": "Accounts payable",
    "shortTermDebt": "Short-term debt",
    "longTermDebt": "Long-term debt",
    "stockholdersEquity": "Stockholders' equity",
    "retainedEarnings": "Retained earnings",
}

CORE_FIELDS = {"assets", "liabilities", "stockholdersEquity", "currentAssets", "currentLiabilities"}

DEFAULT_TARGETS: dict[str, dict[str, Any]] = {
    "currentRatio": {"description": "Current assets divided by current liabilities.", "direction": "higher_is_better", "healthyRange": ">= 1.5", "weight": 0.35},
    "quickRatio": {"description": "Cash, short-term investments, and receivables divided by current liabilities.", "direction": "higher_is_better", "healthyRange": ">= 1.0", "weight": 0.30},
    "cashRatio": {"description": "Cash and equivalents divided by current liabilities.", "direction": "higher_is_better", "healthyRange": ">= 0.5", "weight": 0.20},
    "workingCapital": {"description": "Current assets minus current liabilities.", "direction": "higher_is_better", "healthyRange": "positive", "weight": 0.15},
    "debtToEquity": {"description": "Total debt divided by stockholders' equity.", "direction": "lower_is_better", "healthyRange": "< 0.5", "weight": 0.35},
    "debtToAssets": {"description": "Total debt divided by assets.", "direction": "lower_is_better", "healthyRange": "< 0.30", "weight": 0.30},
    "cashToDebt": {"description": "Cash and equivalents divided by total debt.", "direction": "higher_is_better", "healthyRange": ">= 0.50", "weight": 0.20},
    "shortTermDebtShare": {"description": "Short-term debt divided by total debt.", "direction": "lower_is_better", "healthyRange": "< 0.20", "weight": 0.15},
    "equityRatio": {"description": "Stockholders' equity divided by assets.", "direction": "higher_is_better", "healthyRange": ">= 0.50", "weight": 0.40},
    "netDebt": {"description": "Total debt minus cash and equivalents.", "direction": "lower_is_better", "healthyRange": "negative or low", "weight": 0.15},
    "bookValue": {"description": "Stockholders' equity.", "direction": "higher_is_better", "healthyRange": "positive", "weight": 0.15},
    "goodwillIntangiblesToAssets": {"description": "Goodwill plus intangible assets divided by assets.", "direction": "lower_is_better", "healthyRange": "< 0.25", "weight": 0.50},
    "retainedEarnings": {"description": "Retained earnings or accumulated deficit.", "direction": "higher_is_better", "healthyRange": "positive", "weight": 0.25},
}

STATUS_POINTS = {"healthy": 90, "acceptable": 70, "caution": 55, "risk": 35, "severe_risk": 10, "unavailable": None}


def _round(value: float | None) -> float | None:
    return round(value, 6) if isinstance(value, (int, float)) else None


def _safe_div(numerator: float | None, denominator: float | None, metric: str, warnings: list[str]) -> float | None:
    if numerator is None or denominator is None:
        warnings.append(f"{metric}: missing numerator or denominator")
        return None
    if denominator <= 0:
        warnings.append(f"{metric}: denominator is zero or negative")
        return None
    return _round(numerator / denominator)


def _select_reference(facts: list[FinancialFact]) -> FinancialFact | None:
    core = [fact for fact in facts if fact.form in {"10-K", "10-Q"} and fact.label in {"Assets", "Liabilities", "Stockholders' equity"}]
    return max(core, key=lambda fact: (fact.period_end, fact.filed, fact.form == "10-Q"), default=None)


def _choose_fact(facts: list[FinancialFact], label: str, reference: FinancialFact | None) -> FinancialFact | None:
    candidates = [fact for fact in facts if fact.label == label and fact.form in {"10-K", "10-Q"} and fact.unit == "USD"]
    if not candidates:
        return None
    if reference:
        matched = [fact for fact in candidates if fact.accession == reference.accession and fact.period_end == reference.period_end]
        if matched:
            return max(matched, key=lambda fact: fact.filed)
        matched = [fact for fact in candidates if fact.period_end == reference.period_end]
        if matched:
            return max(matched, key=lambda fact: fact.filed)
    return max(candidates, key=lambda fact: (fact.period_end, fact.filed))


def _value(snapshot: dict[str, Any], key: str) -> float | None:
    value = snapshot.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def build_snapshot(security: Security, facts: list[FinancialFact]) -> dict[str, Any]:
    reference = _select_reference(facts)
    missing: list[str] = []
    warnings: list[str] = []
    snapshot: dict[str, Any] = {
        "schemaVersion": BALANCE_SHEET_SCHEMA_VERSION,
        "ticker": security.ticker,
        "cik": security.cik,
        "companyName": security.company_name,
        "formType": reference.form if reference else None,
        "accession": reference.accession if reference else None,
        "filingDate": reference.filed if reference else None,
        "periodEndDate": reference.period_end if reference else None,
        "fiscalYear": reference.fiscal_year if reference else None,
        "fiscalPeriod": reference.fiscal_period if reference else None,
        "source": "sec_companyfacts" if reference else "unavailable",
        "missingFields": missing,
        "dataQualityWarnings": warnings,
    }
    for key, label in FIELDS.items():
        fact = _choose_fact(facts, label, reference)
        snapshot[key] = _round(fact.value) if fact else None
        if not fact:
            missing.append(key)
            warnings.append(f"{key}: unavailable in SEC companyfacts for selected period")
        elif reference and fact.accession != reference.accession:
            warnings.append(f"{key}: used same-period or latest fact from a different accession")
    if snapshot["assets"] is None or snapshot["liabilities"] is None or snapshot["stockholdersEquity"] is None:
        snapshot["source"] = "unavailable" if not reference else "sec_companyfacts"
    return snapshot


def derive_metrics(snapshot: dict[str, Any], *, market_cap: float | None = None, shares_outstanding: float | None = None) -> dict[str, Any]:
    warnings: list[str] = []
    current_assets = _value(snapshot, "currentAssets")
    current_liabilities = _value(snapshot, "currentLiabilities")
    cash = _value(snapshot, "cashAndEquivalents")
    investments = _value(snapshot, "shortTermInvestments") or 0
    receivables = _value(snapshot, "accountsReceivable") or 0
    assets = _value(snapshot, "assets")
    equity = _value(snapshot, "stockholdersEquity")
    short_debt = _value(snapshot, "shortTermDebt")
    long_debt = _value(snapshot, "longTermDebt")
    goodwill = _value(snapshot, "goodwill") or 0
    intangibles = _value(snapshot, "intangibleAssets") or 0
    retained = _value(snapshot, "retainedEarnings")
    total_debt = _round((short_debt or 0) + (long_debt or 0)) if short_debt is not None or long_debt is not None else None
    snapshot["totalDebt"] = total_debt
    metrics = {
        "currentRatio": _safe_div(current_assets, current_liabilities, "currentRatio", warnings),
        "quickRatio": _safe_div((cash or 0) + investments + receivables if cash is not None else None, current_liabilities, "quickRatio", warnings),
        "cashRatio": _safe_div(cash, current_liabilities, "cashRatio", warnings),
        "workingCapital": _round(current_assets - current_liabilities) if current_assets is not None and current_liabilities is not None else None,
        "debtToEquity": _safe_div(total_debt, equity, "debtToEquity", warnings),
        "debtToAssets": _safe_div(total_debt, assets, "debtToAssets", warnings),
        "equityRatio": _safe_div(equity, assets, "equityRatio", warnings),
        "cashToDebt": _safe_div(cash, total_debt, "cashToDebt", warnings) if total_debt != 0 else None,
        "netDebt": _round(total_debt - cash) if total_debt is not None and cash is not None else None,
        "goodwillIntangiblesToAssets": _safe_div(goodwill + intangibles, assets, "goodwillIntangiblesToAssets", warnings),
        "shortTermDebtShare": _safe_div(short_debt, total_debt, "shortTermDebtShare", warnings) if total_debt != 0 else None,
        "bookValue": equity,
        "bookValuePerShare": _safe_div(equity, shares_outstanding, "bookValuePerShare", warnings),
        "priceToBook": _safe_div(market_cap, equity, "priceToBook", warnings),
        "retainedEarnings": retained,
    }
    if total_debt == 0 and cash and cash > 0:
        warnings.append("cashToDebt: total debt is zero and cash is positive; cash coverage is very strong")
    if equity is not None and equity <= 0:
        warnings.append("Negative equity: stockholders' equity is zero or negative")
    return {"schemaVersion": BALANCE_SHEET_SCHEMA_VERSION, "metrics": metrics, "warnings": warnings}


def _band(metric: str, value: float | None, metrics: dict[str, Any]) -> str:
    if value is None:
        return "unavailable"
    if metric in {"currentRatio"}:
        return "healthy" if value >= 1.5 else "acceptable" if value >= 1.0 else "risk" if value >= 0.75 else "severe_risk"
    if metric == "quickRatio":
        return "healthy" if value >= 1.0 else "acceptable" if value >= 0.75 else "risk" if value >= 0.5 else "severe_risk"
    if metric == "cashRatio":
        return "healthy" if value >= 0.5 else "acceptable" if value >= 0.25 else "risk" if value >= 0.1 else "severe_risk"
    if metric == "workingCapital":
        if value >= 0: return "healthy"
        current_ratio = metrics.get("currentRatio")
        quick_ratio = metrics.get("quickRatio")
        return "severe_risk" if isinstance(current_ratio, (int, float)) and current_ratio < 0.75 and isinstance(quick_ratio, (int, float)) and quick_ratio < 0.5 else "risk"
    if metric == "debtToEquity":
        return "healthy" if value < 0.5 else "acceptable" if value <= 1.5 else "risk" if value <= 3.0 else "severe_risk"
    if metric == "debtToAssets":
        return "healthy" if value < 0.30 else "acceptable" if value <= 0.50 else "risk" if value <= 0.70 else "severe_risk"
    if metric == "equityRatio":
        return "healthy" if value >= 0.50 else "acceptable" if value >= 0.30 else "risk" if value >= 0.20 else "severe_risk"
    if metric == "cashToDebt":
        return "healthy" if value >= 0.50 else "acceptable" if value >= 0.20 else "risk" if value >= 0.10 else "severe_risk"
    if metric == "shortTermDebtShare":
        return "healthy" if value < 0.20 else "acceptable" if value <= 0.40 else "risk" if value <= 0.60 else "severe_risk"
    if metric == "goodwillIntangiblesToAssets":
        return "healthy" if value < 0.25 else "acceptable" if value <= 0.40 else "risk" if value <= 0.60 else "severe_risk"
    if metric in {"bookValue", "retainedEarnings"}:
        return "healthy" if value >= 0 else "risk"
    if metric == "netDebt":
        debt_assets = metrics.get("debtToAssets")
        current_ratio = metrics.get("currentRatio")
        if value <= 0: return "healthy"
        if isinstance(debt_assets, (int, float)) and debt_assets > 0.6 and isinstance(current_ratio, (int, float)) and current_ratio < 1.0:
            return "risk"
        return "acceptable"
    return "unavailable"


def _comparison(metric: str, value: float | None, metrics: dict[str, Any]) -> dict[str, Any]:
    target = DEFAULT_TARGETS.get(metric, {})
    status = _band(metric, value, metrics)
    return {
        "metric": metric,
        "value": value,
        "status": status,
        "healthyRange": target.get("healthyRange", "not defined"),
        "interpretation": _interpret(metric, status),
        "weight": target.get("weight", 0),
    }


def _interpret(metric: str, status: str) -> str:
    if status == "unavailable":
        return f"{metric} could not be computed from available balance-sheet facts."
    if status == "healthy":
        return f"{metric} is in the preferred screening range."
    if status == "acceptable":
        return f"{metric} is usable but not especially strong."
    if status == "risk":
        return f"{metric} is outside the preferred range and weakens balance-sheet evidence."
    return f"{metric} is in the severe-risk range and should be reviewed before relying on the signal."


def _weighted_average(comparisons: list[dict[str, Any]], weights: dict[str, float]) -> float | None:
    available = []
    for item in comparisons:
        points = STATUS_POINTS.get(item["status"])
        weight = weights.get(item["metric"], 0)
        if points is not None and weight:
            available.append((points, weight))
    total = sum(weight for _, weight in available)
    return _round(sum(points * weight for points, weight in available) / total) if total else None


def _gate(name: str, severity: str, triggered: bool, explanation: str, metrics: list[str]) -> dict[str, Any]:
    return {"name": name, "severity": severity, "triggered": triggered, "explanation": explanation, "metrics": metrics}


def score_balance_sheet(snapshot: dict[str, Any], metrics_payload: dict[str, Any]) -> dict[str, Any]:
    metrics = metrics_payload.get("metrics", {})
    comparisons = [_comparison(metric, metrics.get(metric), metrics) for metric in DEFAULT_TARGETS]
    current_ratio, quick_ratio, cash_ratio = metrics.get("currentRatio"), metrics.get("quickRatio"), metrics.get("cashRatio")
    working_capital = metrics.get("workingCapital")
    debt_to_equity, debt_to_assets = metrics.get("debtToEquity"), metrics.get("debtToAssets")
    equity = snapshot.get("stockholdersEquity")
    cash_to_debt, short_debt_share = metrics.get("cashToDebt"), metrics.get("shortTermDebtShare")
    goodwill_ratio = metrics.get("goodwillIntangiblesToAssets")
    gates = [
        _gate("Liquidity Risk Gate", "moderate", any(isinstance(v, (int, float)) and v < t for v, t in ((current_ratio, 1.0), (quick_ratio, 0.75), (cash_ratio, 0.10))) or (isinstance(working_capital, (int, float)) and working_capital < 0), "Liquidity metrics are below preferred thresholds.", ["currentRatio", "quickRatio", "cashRatio", "workingCapital"]),
        _gate("Severe Liquidity Risk Gate", "severe", isinstance(current_ratio, (int, float)) and current_ratio < 0.75 and isinstance(quick_ratio, (int, float)) and quick_ratio < 0.50, "Both current and quick ratios are severely weak.", ["currentRatio", "quickRatio"]),
        _gate("High Leverage Gate", "high", (isinstance(debt_to_equity, (int, float)) and debt_to_equity > 2.0) or (isinstance(debt_to_assets, (int, float)) and debt_to_assets > 0.60), "Leverage is elevated versus default target bands.", ["debtToEquity", "debtToAssets"]),
        _gate("Severe Leverage Gate", "severe", (isinstance(debt_to_equity, (int, float)) and debt_to_equity > 3.0) or (isinstance(debt_to_assets, (int, float)) and debt_to_assets > 0.70), "Leverage is in the severe-risk range.", ["debtToEquity", "debtToAssets"]),
        _gate("Negative Equity Gate", "severe", isinstance(equity, (int, float)) and equity <= 0, "Stockholders' equity is zero or negative.", ["stockholdersEquity"]),
        _gate("Debt Maturity Pressure Gate", "high", isinstance(short_debt_share, (int, float)) and short_debt_share > 0.40 and isinstance(cash_to_debt, (int, float)) and cash_to_debt < 0.20, "Short-term debt is high and cash coverage is weak.", ["shortTermDebtShare", "cashToDebt"]),
        _gate("Asset Quality Warning Gate", "warning", isinstance(goodwill_ratio, (int, float)) and goodwill_ratio > 0.50, "Goodwill and intangibles are high relative to assets.", ["goodwillIntangiblesToAssets"]),
        _gate("Balance Sheet Incomplete Gate", "warning", any(field in set(snapshot.get("missingFields", [])) for field in CORE_FIELDS), "Core balance-sheet fields are missing.", sorted(CORE_FIELDS)),
    ]
    liquidity = _weighted_average(comparisons, {"currentRatio": .35, "quickRatio": .30, "cashRatio": .20, "workingCapital": .15})
    leverage = _weighted_average(comparisons, {"debtToEquity": .35, "debtToAssets": .30, "cashToDebt": .20, "shortTermDebtShare": .15})
    solvency = _weighted_average(comparisons, {"equityRatio": .40, "debtToAssets": .30, "netDebt": .15, "bookValue": .15})
    asset_quality = _weighted_average(comparisons, {"goodwillIntangiblesToAssets": .50, "retainedEarnings": .25, "bookValue": .25})
    if any(g["triggered"] and g["name"] == "Negative Equity Gate" for g in gates):
        leverage = min(leverage or 15, 15)
        solvency = min(solvency or 15, 15)
    if any(g["triggered"] and g["name"] == "Severe Liquidity Risk Gate" for g in gates):
        liquidity = min(liquidity or 20, 20)
    if any(g["triggered"] and g["name"] == "Severe Leverage Gate" for g in gates):
        leverage = min(leverage or 20, 20)
    quality = _weighted_average([
        {"metric": "liquidity", "status": _points_to_status(liquidity)},
        {"metric": "leverage", "status": _points_to_status(leverage)},
        {"metric": "solvency", "status": _points_to_status(solvency)},
        {"metric": "assetQuality", "status": _points_to_status(asset_quality)},
    ], {"liquidity": .30, "leverage": .30, "solvency": .30, "assetQuality": .10})
    risk_penalty = None if quality is None else 100 - quality
    penalties = {"Negative Equity Gate": 30, "Severe Liquidity Risk Gate": 25, "Severe Leverage Gate": 25, "Debt Maturity Pressure Gate": 15, "Asset Quality Warning Gate": 10, "Balance Sheet Incomplete Gate": 10}
    if risk_penalty is not None:
        risk_penalty = min(100, risk_penalty + sum(points for gate, points in penalties.items() if any(g["triggered"] and g["name"] == gate for g in gates)))
    confidence_adjustment = _confidence_adjustment(snapshot, gates)
    return {
        "schemaVersion": BALANCE_SHEET_SCHEMA_VERSION,
        "liquidityScore": liquidity,
        "leverageScore": leverage,
        "solvencyScore": solvency,
        "assetQualityScore": asset_quality,
        "balanceSheetQualityScore": quality,
        "balanceSheetRiskPenalty": _round(risk_penalty),
        "triggeredRiskGates": gates,
        "targetComparisons": comparisons,
        "confidenceAdjustment": confidence_adjustment,
        "warnings": list(dict.fromkeys([*snapshot.get("dataQualityWarnings", []), *metrics_payload.get("warnings", [])])),
    }


def _points_to_status(points: float | None) -> str:
    if points is None: return "unavailable"
    if points >= 80: return "healthy"
    if points >= 60: return "acceptable"
    if points >= 40: return "caution"
    if points >= 20: return "risk"
    return "severe_risk"


def _confidence_adjustment(snapshot: dict[str, Any], gates: list[dict[str, Any]]) -> int:
    missing = set(snapshot.get("missingFields", []))
    if snapshot.get("source") == "unavailable":
        return -15
    adjustment = 5 if not missing else 0
    if missing & {"assets", "liabilities", "stockholdersEquity"}:
        adjustment -= 10
    if missing & {"currentAssets", "currentLiabilities"}:
        adjustment -= 5
    elif missing:
        adjustment -= 3
    if any(gate["triggered"] and gate["name"] == "Balance Sheet Incomplete Gate" for gate in gates):
        adjustment -= 5
    return max(-20, min(5, adjustment))


def experimental_signal(current_signal: str, scores: dict[str, Any], scoring: dict[str, Any]) -> dict[str, Any]:
    gates = [gate for gate in scoring.get("triggeredRiskGates", []) if gate.get("triggered")]
    gate_names = [gate["name"] for gate in gates]
    severe = any(gate.get("severity") == "severe" for gate in gates)
    risk_penalty = scoring.get("balanceSheetRiskPenalty")
    quality = scoring.get("balanceSheetQualityScore")
    value = scores.get("value")
    business_quality = scores.get("quality")
    candidate = current_signal
    reasons: list[str] = []
    if value is not None and value >= 65 and (severe or (risk_penalty is not None and risk_penalty >= 70)):
        candidate = "value-trap-risk"
        reasons.append("Strong value evidence is paired with elevated balance-sheet risk.")
    elif current_signal == "potentially-undervalued" and (severe or (quality is not None and quality < 60)):
        candidate = "neutral"
        reasons.append("Balance-sheet quality is not acceptable enough for a clean undervaluation signal.")
    elif current_signal == "quality-watchlist" and (severe or (quality is not None and quality < 60)):
        candidate = "neutral"
        reasons.append("Balance-sheet weakness complicates the quality watchlist case.")
    elif business_quality is not None and business_quality >= 70 and quality is not None and quality >= 60 and current_signal == "neutral":
        reasons.append("Balance-sheet evidence supports quality, but official signal remains pipeline-controlled.")
    return {"signal": candidate, "previousOfficialSignal": current_signal, "changed": candidate != current_signal, "reasons": reasons, "triggeredGates": gate_names}


def balance_sheet_bundle(security: Security, facts: list[FinancialFact], *, market_cap: float | None = None,
                         shares_outstanding: float | None = None) -> dict[str, Any]:
    snapshot = build_snapshot(security, facts)
    metrics = derive_metrics(snapshot, market_cap=market_cap, shares_outstanding=shares_outstanding)
    scoring = score_balance_sheet(snapshot, metrics)
    return {"snapshot": snapshot, "metrics": metrics["metrics"], "metricWarnings": metrics["warnings"], "scoring": scoring}


def write_balance_sheet_artifacts(bundles: dict[str, dict[str, Any]], output_root: Path = Path("data")) -> dict[str, Any]:
    balance_dir = output_root / "fundamentals" / "balance_sheets"
    report_dir = output_root / "reports"
    balance_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    missing_counts: dict[str, int] = {}
    source_breakdown: dict[str, int] = {}
    warnings: list[str] = []
    for ticker, bundle in sorted(bundles.items()):
        snapshot = bundle["snapshot"]
        for field in snapshot.get("missingFields", []):
            missing_counts[field] = missing_counts.get(field, 0) + 1
        source = snapshot.get("source", "unavailable")
        source_breakdown[source] = source_breakdown.get(source, 0) + 1
        warnings.extend(f"{ticker}: {warning}" for warning in bundle.get("scoring", {}).get("warnings", [])[:3])
        (balance_dir / f"{ticker}.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    available = sum(1 for bundle in bundles.values() if not bundle["snapshot"].get("missingFields"))
    partial = sum(1 for bundle in bundles.values() if bundle["snapshot"].get("source") != "unavailable" and bundle["snapshot"].get("missingFields"))
    manifest = {
        "schemaVersion": BALANCE_SHEET_SCHEMA_VERSION,
        "companiesAttempted": len(bundles),
        "balanceSheetsAvailable": available,
        "balanceSheetsPartial": partial,
        "unavailableCompanies": sum(1 for bundle in bundles.values() if bundle["snapshot"].get("source") == "unavailable"),
        "missingFieldCounts": dict(sorted(missing_counts.items())),
        "sourceBreakdown": dict(sorted(source_breakdown.items())),
        "warnings": warnings[:200],
    }
    (balance_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (report_dir / "balance_sheet_coverage_report.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
