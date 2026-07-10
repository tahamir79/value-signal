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

SIGNAL_LABELS = {
    "potentially-undervalued": "Potentially undervalued",
    "quality-watchlist": "Quality watchlist",
    "value-trap-risk": "Value trap risk",
    "momentum-risk": "Momentum risk",
    "neutral": "Neutral",
    "insufficient-evidence": "Insufficient evidence",
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
        "confidence": (signal_row or {}).get("confidence"),
        "asOf": (signal_row or feature_row or {}).get("asOf"),
        "scores": (signal_row or {}).get("scores") or {},
        "components": (signal_row or {}).get("components") or {},
        "rawFeatures": (feature_row or {}).get("raw") or {},
        "percentiles": (feature_row or {}).get("percentile") or {},
        "missingFeatures": [key for key, missing in ((feature_row or {}).get("missing") or {}).items() if missing],
        "rangeWarnings": (feature_row or {}).get("rangeWarnings") or [],
        "derived": (dashboard_row or {}).get("derived") or {},
        "latestFacts": (dashboard_row or {}).get("latestFacts") or {},
    }


def stock_context_summary(context: dict[str, Any] | None, *, max_facts: int = 6) -> str:
    if not context:
        return "Structured pipeline context: Not available."
    scores = context.get("scores") or {}
    raw = context.get("rawFeatures") or {}
    derived = context.get("derived") or {}
    facts = context.get("latestFacts") or {}
    fact_lines = []
    for name, fact in list(facts.items())[:max_facts]:
        if not isinstance(fact, dict):
            continue
        fact_lines.append(
            f"- {name}: {fact.get('value')} {fact.get('unit', '')} "
            f"(period_end={fact.get('period_end')}, form={fact.get('form')}, filed={fact.get('filed')})"
        )
    return "\n".join([
        "Structured pipeline context:",
        f"- Official deterministic signal: {context.get('officialSignalLabel') or 'Not available'} ({context.get('officialSignal') or 'unknown'})",
        f"- Signal confidence: {context.get('confidence') or 'Not available'}",
        f"- As of: {context.get('asOf') or 'Not available'}",
        "- Component scores: " + (", ".join(f"{key}={value}" for key, value in scores.items()) or "Not available"),
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


def extract_evidence_assessment(answer: str | None) -> str:
    if not answer:
        return "Insufficient evidence"
    for line in answer.splitlines():
        label, sep, value = line.partition(":")
        if sep and label.strip().lower().replace("_", " ") in {"evidence assessment", "evidence_assessment"}:
            return normalize_evidence_assessment(value)
    return normalize_evidence_assessment(answer[:240])
