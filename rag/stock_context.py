from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVIDENCE_ASSESSMENTS = {
    "Supports signal",
    "Weakens signal",
    "Mixed evidence",
    "Insufficient evidence",
    "Review recommended",
}

EVIDENCE_RELEVANCE_VALUES = {
    "Directly relevant to question",
    "Partially relevant",
    "Weakly relevant",
    "Insufficient evidence",
}

SIGNAL_RELATIONSHIP_VALUES = {
    "Supports signal",
    "Weakens signal",
    "Mixed",
    "Indirect relationship",
    "Not enough evidence to connect to signal",
    "Review recommended",
}

SIGNAL_LABELS = {
    "potentially-undervalued": "Potentially undervalued",
    "quality-watchlist": "Quality watchlist",
    "value-trap-risk": "Value trap risk",
    "momentum-risk": "Momentum risk",
    "neutral": "Neutral",
    "insufficient-evidence": "Insufficient evidence",
}

SIGNAL_DEFINITIONS = {
    "potentially-undervalued": "Value appears favorable relative to the current universe, subject to quality and risk checks.",
    "quality-watchlist": "Quality or operating signals are relatively strong, but valuation or risk may still need review.",
    "value-trap-risk": "Value appears attractive, but quality, balance-sheet, momentum, or other risk evidence may weaken the case.",
    "momentum-risk": "Recent price or volatility behavior raises caution despite other possible strengths.",
    "neutral": "The evidence does not strongly support a positive or negative research theme.",
    "insufficient-evidence": "The pipeline does not have enough evidence to assign a confident research theme.",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _records(path: Path) -> list[dict[str, Any]]:
    payload = _load(path)
    rows = payload.get("records") or payload.get("signals") or payload.get("features") or []
    return rows if isinstance(rows, list) else []


def _ticker(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or row.get("security", {}).get("ticker", "")).upper()


def _find(path: Path, ticker: str) -> dict[str, Any] | None:
    wanted = ticker.upper()
    for row in _records(path):
        if _ticker(row) == wanted:
            return row
    return None


def build_stock_context(
    ticker: str | None,
    *,
    signals_path: Path = Path("public/data/signals.json"),
    features_path: Path = Path("public/data/features.json"),
    dashboard_path: Path = Path("public/data/dashboard.json"),
) -> dict[str, Any] | None:
    if not ticker:
        return None
    ticker = ticker.upper()
    signal_row = _find(signals_path, ticker)
    feature_row = _find(features_path, ticker)
    dashboard_row = _find(dashboard_path, ticker)
    if not any((signal_row, feature_row, dashboard_row)):
        return None
    security = (dashboard_row or {}).get("security", {})
    signal_key = (signal_row or {}).get("signal") or (signal_row or {}).get("primarySignal")
    return {
        "ticker": ticker,
        "companyName": (signal_row or {}).get("companyName") or security.get("company_name"),
        "officialSignal": signal_key,
        "officialSignalLabel": SIGNAL_LABELS.get(str(signal_key), signal_key),
        "signalDefinition": SIGNAL_DEFINITIONS.get(str(signal_key), "Definition unavailable."),
        "confidence": (signal_row or {}).get("confidence"),
        "asOf": (signal_row or feature_row or {}).get("asOf"),
        "reasonCodes": (signal_row or {}).get("reasonCodes") or [],
        "explanations": (signal_row or {}).get("explanations") or [],
        "scores": (signal_row or {}).get("scores") or {},
        "components": (signal_row or {}).get("components") or {},
        "rawFeatures": (feature_row or {}).get("raw") or {},
        "percentiles": (feature_row or {}).get("percentile") or {},
        "missingFeatures": [key for key, missing in ((feature_row or {}).get("missing") or {}).items() if missing],
        "rangeWarnings": (feature_row or {}).get("rangeWarnings") or [],
        "derived": (dashboard_row or {}).get("derived") or {},
        "latestFacts": (dashboard_row or {}).get("latestFacts") or {},
        "balanceSheet": {
            "snapshot": (dashboard_row or {}).get("balanceSheet") or {},
            "metrics": (dashboard_row or {}).get("balanceSheetMetrics") or {},
            "scoring": (dashboard_row or {}).get("balanceSheetScoringShadow") or (signal_row or {}).get("balanceSheetScoringShadow") or {},
            "targetComparisons": ((dashboard_row or {}).get("balanceSheetScoringShadow") or (signal_row or {}).get("balanceSheetScoringShadow") or {}).get("targetComparisons") or [],
            "riskGates": ((dashboard_row or {}).get("balanceSheetScoringShadow") or (signal_row or {}).get("balanceSheetScoringShadow") or {}).get("triggeredRiskGates") or [],
        },
    }


def inferred_risk_gates(context: dict[str, Any] | None) -> list[str]:
    if not context:
        return []
    gates: list[str] = []
    scores = context.get("scores") or {}
    for key, label in {
        "marketRisk": "Elevated market risk score",
        "balanceSheetRisk": "Elevated balance-sheet risk score",
        "momentumRisk": "Elevated momentum-risk score",
    }.items():
        value = scores.get(key)
        if isinstance(value, (int, float)) and value >= 70:
            gates.append(f"{label} ({value})")
    for reason in context.get("reasonCodes") or []:
        text = str(reason)
        if "risk" in text.lower() and text not in gates:
            gates.append(text)
    return gates


def stock_context_summary(context: dict[str, Any] | None, *, max_facts: int = 6, detail: str = "compact") -> str:
    if not context:
        return "Structured pipeline context: Not available."
    scores = context.get("scores") or {}
    raw = context.get("rawFeatures") or {}
    derived = context.get("derived") or {}
    facts = context.get("latestFacts") or {}
    balance_sheet = context.get("balanceSheet") or {}
    balance_scoring = balance_sheet.get("scoring") or {}
    gates = inferred_risk_gates(context)
    bs_gates = [gate.get("name") for gate in balance_scoring.get("triggeredRiskGates", []) if isinstance(gate, dict) and gate.get("triggered")]
    fact_lines = []
    for name, fact in list(facts.items())[:max_facts]:
        if not isinstance(fact, dict):
            continue
        fact_lines.append(
            f"- {name}: {fact.get('value')} {fact.get('unit', '')} "
            f"(period_end={fact.get('period_end')}, form={fact.get('form')}, filed={fact.get('filed')})"
        )
    compact_lines = [
        "Structured pipeline context:",
        "- Use this as background context. Do not restate these fields unless they directly change the answer.",
        f"- Official deterministic signal: {context.get('officialSignalLabel') or 'Not available'} ({context.get('officialSignal') or 'unknown'})",
        f"- Signal definition: {context.get('signalDefinition') or 'Not available'}",
        f"- Signal confidence: {context.get('confidence') or 'Not available'}",
        f"- As of: {context.get('asOf') or 'Not available'}",
        "- Risk gates triggered: " + (", ".join(gates) or "None inferred"),
        "- Balance-sheet shadow scores: "
        + (
            f"quality={balance_scoring.get('balanceSheetQualityScore')}, "
            f"riskPenalty={balance_scoring.get('balanceSheetRiskPenalty')}, "
            f"liquidity={balance_scoring.get('liquidityScore')}, "
            f"leverage={balance_scoring.get('leverageScore')}, "
            f"solvency={balance_scoring.get('solvencyScore')}"
            if balance_scoring else "Not available"
        ),
        "- Balance-sheet gates: " + (", ".join(str(value) for value in bs_gates) or "None recorded"),
        "- Reason codes: " + (", ".join(str(value) for value in (context.get("reasonCodes") or [])) or "None recorded"),
    ]
    if detail != "full":
        return "\n".join(compact_lines)
    return "\n".join([
        *compact_lines,
        "- Component scores: " + (", ".join(f"{key}={value}" for key, value in scores.items()) or "Not available"),
        "- Explanations: " + (" | ".join(str(value) for value in (context.get("explanations") or [])) or "None recorded"),
        "- Raw features: " + (", ".join(f"{key}={value}" for key, value in raw.items()) or "Not available"),
        "- Derived dashboard fields: " + (", ".join(f"{key}={value}" for key, value in derived.items()) or "Not available"),
        "- Missing features: " + (", ".join(context.get("missingFeatures") or []) or "None recorded"),
        "- Latest facts:",
        *(fact_lines or ["- Not available"]),
    ])


def normalize_evidence_assessment(value: str | None) -> str:
    if not value:
        return "Insufficient evidence"
    cleaned = value.strip().strip(":.-")
    for allowed in EVIDENCE_ASSESSMENTS:
        if cleaned.lower() == allowed.lower():
            return allowed
    lowered = cleaned.lower()
    if "review" in lowered:
        return "Review recommended"
    if "weak" in lowered or "contradict" in lowered:
        return "Weakens signal"
    if "support" in lowered:
        return "Supports signal"
    if "mixed" in lowered or "complicat" in lowered:
        return "Mixed evidence"
    return "Insufficient evidence"


def normalize_evidence_relevance(value: str | None) -> str:
    if not value:
        return "Insufficient evidence"
    lowered = value.lower()
    if "direct" in lowered:
        return "Directly relevant to question"
    if "partial" in lowered:
        return "Partially relevant"
    if "weak" in lowered:
        return "Weakly relevant"
    return "Insufficient evidence"


def normalize_signal_relationship(value: str | None) -> str:
    if not value:
        return "Not enough evidence to connect to signal"
    lowered = value.lower()
    if "review" in lowered:
        return "Review recommended"
    if "indirect" in lowered:
        return "Indirect relationship"
    if "not enough" in lowered or "insufficient" in lowered:
        return "Not enough evidence to connect to signal"
    if "weak" in lowered:
        return "Weakens signal"
    if "mixed" in lowered or "complicat" in lowered:
        return "Mixed"
    if "support" in lowered:
        return "Supports signal"
    return "Not enough evidence to connect to signal"


def extract_evidence_assessment(answer: str | None) -> str:
    if not answer:
        return "Insufficient evidence"
    for line in answer.splitlines():
        label, sep, value = line.partition(":")
        if sep and label.strip().lower().replace("_", " ") in {"evidence assessment", "evidence_assessment"}:
            return normalize_evidence_assessment(value)
    return normalize_evidence_assessment(answer[:240])


def extract_named_field(answer: str | None, names: set[str]) -> str | None:
    if not answer:
        return None
    normalized_names = {name.lower().replace("_", " ") for name in names}
    for line in answer.splitlines():
        label, sep, value = line.partition(":")
        if sep and label.strip().lower().replace("_", " ") in normalized_names:
            return value.strip()
    return None
