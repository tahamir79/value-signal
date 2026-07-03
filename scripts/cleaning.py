from __future__ import annotations
from datetime import date
from typing import Any
from scripts.models import FinancialFact

CONCEPTS = {
    "Revenues": ("Revenue", ("USD",)),
    "RevenueFromContractWithCustomerExcludingAssessedTax": ("Revenue", ("USD",)),
    "NetIncomeLoss": ("Net income", ("USD",)),
    "Assets": ("Assets", ("USD",)),
    "Liabilities": ("Liabilities", ("USD",)),
    "StockholdersEquity": ("Stockholders' equity", ("USD",)),
    "EntityCommonStockSharesOutstanding": ("Shares outstanding", ("shares",)),
}

def _iso(value: str) -> str:
    return date.fromisoformat(value).isoformat()

def normalize_company_facts(payload: dict[str, Any]) -> list[FinancialFact]:
    gaap = payload.get("facts", {}).get("us-gaap", {})
    dei = payload.get("facts", {}).get("dei", {})
    source = {**gaap, **dei}
    normalized: list[FinancialFact] = []
    for concept, (label, units) in CONCEPTS.items():
        node = source.get(concept, {})
        for unit in units:
            for item in node.get("units", {}).get(unit, []):
                if item.get("form") not in {"10-K", "10-Q"} or item.get("val") is None:
                    continue
                try:
                    normalized.append(FinancialFact(concept, label, float(item["val"]), unit, _iso(item["end"]), _iso(item["filed"]), item.get("fy"), item.get("fp"), item["form"], item.get("accn", "")))
                except (TypeError, ValueError, KeyError):
                    continue
    return sorted(normalized, key=lambda fact: (fact.concept, fact.period_end, fact.filed))

def latest_facts(facts: list[FinancialFact]) -> dict[str, FinancialFact]:
    result: dict[str, FinancialFact] = {}
    for fact in facts:
        prior = result.get(fact.label)
        if prior is None or (fact.period_end, fact.filed) > (prior.period_end, prior.filed):
            result[fact.label] = fact
    return result
