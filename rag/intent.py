from __future__ import annotations

import re
from typing import Any

RISK_OUTLOOK_INTENT = "risk_outlook"
GENERAL_INTENT = "general"

RISK_OUTLOOK_PATTERNS = [
    r"\bgo\s+up\b",
    r"\bgo\s+down\b",
    r"\bup\s+or\s+down\b",
    r"\bhold\s+value\b",
    r"\bprice\s+direction\b",
    r"\bdownside\s+risk\b",
    r"\bupside\s+support\b",
    r"\brisk[-\s]?based\s+outlook\b",
    r"\bexpect\s+(?:it|this|the stock)\s+to\s+recover\b",
    r"\brecover\b",
    r"\bsignal\s+strong\s+enough\b",
    r"\bstrong\s+enough\b",
]

RISK_EVIDENCE_QUERY = (
    "Risk Factors market risk liquidity debt margin pressure material weakness "
    "macroeconomic pressure customer concentration demand weakness competition"
)

SUPPORT_EVIDENCE_QUERY = (
    "MD&A results of operations revenue growth operating income cash flow demand "
    "business outlook liquidity strength capital resources"
)


def detect_intent(query: str) -> str:
    lowered = query.lower()
    return RISK_OUTLOOK_INTENT if any(re.search(pattern, lowered) for pattern in RISK_OUTLOOK_PATTERNS) else GENERAL_INTENT


def expanded_queries(query: str, intent: str) -> list[tuple[str, str]]:
    if intent != RISK_OUTLOOK_INTENT:
        return [("primary", query)]
    return [
        ("primary", query),
        ("risk", f"{query} {RISK_EVIDENCE_QUERY}"),
        ("support", f"{query} {SUPPORT_EVIDENCE_QUERY}"),
    ]


def deterministic_risk_posture(context: dict[str, Any] | None) -> str:
    if not context:
        return "insufficient"
    scores = context.get("scores") or {}
    risk_values = [
        value for key, value in scores.items()
        if key in {"marketRisk", "balanceSheetRisk", "momentumRisk"} and isinstance(value, (int, float))
    ]
    value_score = scores.get("value")
    quality_score = scores.get("quality")
    if any(value >= 75 for value in risk_values):
        return "elevated risk"
    if isinstance(value_score, (int, float)) and isinstance(quality_score, (int, float)) and value_score >= 65 and quality_score >= 55:
        return "supportive"
    if risk_values or scores:
        return "mixed"
    return "insufficient"
