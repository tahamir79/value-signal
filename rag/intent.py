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

INTENT_KEYWORDS = {
    "cybersecurity_risk_review": ("cybersecurity", "incident", "security controls", "risk management practices"),
    "value_trap_risk": ("value trap", "cheap", "valuation risk", "value risk"),
    "undervaluation_support": ("undervalued", "undervaluation", "valuation support"),
    "liquidity_debt_risk": ("liquidity", "debt", "capital resources", "cash requirements"),
    "margin_pressure": ("margin pressure", "gross margin", "operating margin", "cost pressure"),
    "demand_revenue_weakness": ("demand", "revenue weakness", "sales decline", "revenue growth"),
    "catalyst_review": ("catalyst", "new product", "launch", "business outlook"),
    "follow_up_research": ("further review", "research next", "specific mitigation", "impact on the company", "detailed assessment"),
}

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
    if any(re.search(pattern, lowered) for pattern in RISK_OUTLOOK_PATTERNS):
        return RISK_OUTLOOK_INTENT
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent
    return GENERAL_INTENT


def expanded_queries(query: str, intent: str) -> list[tuple[str, str]]:
    if intent != RISK_OUTLOOK_INTENT:
        return [("primary", query)]
    return [
        ("primary", query),
        ("risk", f"{query} {RISK_EVIDENCE_QUERY}"),
        ("support", f"{query} {SUPPORT_EVIDENCE_QUERY}"),
    ]


def intent_retrieval_queries(query: str, intent: str) -> list[tuple[str, str]]:
    if intent == RISK_OUTLOOK_INTENT:
        return expanded_queries(query, intent)
    bundles = {
        "cybersecurity_risk_review": "Item 1C cybersecurity risk management governance incident response controls third party information systems",
        "value_trap_risk": "Risk Factors MD&A value trap quality weakness leverage margin pressure demand debt",
        "undervaluation_support": "MD&A revenue growth operating income cash flow liquidity valuation support business outlook",
        "liquidity_debt_risk": "Liquidity and Capital Resources debt maturities cash flow credit facilities capital requirements",
        "margin_pressure": "gross margin margin pressure costs tariffs pricing competition operating income",
        "demand_revenue_weakness": "demand revenue growth sales weakness competition macroeconomic pressure results of operations",
        "catalyst_review": "business outlook product launch demand growth operating results management discussion",
        "follow_up_research": "Risk Factors MD&A Item 1C Controls and Procedures financial impact mitigation costs governance",
    }
    if intent in bundles:
        return [("primary", query), ("intent", f"{query} {bundles[intent]}")]
    return [("primary", query)]


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
