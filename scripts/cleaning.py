from __future__ import annotations
from datetime import date
from typing import Any
from scripts.models import FinancialFact

CONCEPTS = {
    "Revenues": ("Revenue", ("USD",)),
    "RevenueFromContractWithCustomerExcludingAssessedTax": ("Revenue", ("USD",)),
    "NetIncomeLoss": ("Net income", ("USD",)),
    "Assets": ("Assets", ("USD",)),
    "AssetsCurrent": ("Current assets", ("USD",)),
    "CashAndCashEquivalentsAtCarryingValue": ("Cash and equivalents", ("USD",)),
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": ("Cash and equivalents", ("USD",)),
    "ShortTermInvestments": ("Short-term investments", ("USD",)),
    "MarketableSecuritiesCurrent": ("Short-term investments", ("USD",)),
    "AccountsReceivableNetCurrent": ("Accounts receivable", ("USD",)),
    "InventoryNet": ("Inventory", ("USD",)),
    "PropertyPlantAndEquipmentNet": ("Property plant and equipment, net", ("USD",)),
    "Goodwill": ("Goodwill", ("USD",)),
    "IntangibleAssetsNetExcludingGoodwill": ("Intangible assets", ("USD",)),
    "FiniteLivedIntangibleAssetsNet": ("Intangible assets", ("USD",)),
    "Liabilities": ("Liabilities", ("USD",)),
    "LiabilitiesCurrent": ("Current liabilities", ("USD",)),
    "AccountsPayableCurrent": ("Accounts payable", ("USD",)),
    "ShortTermBorrowings": ("Short-term debt", ("USD",)),
    "LongTermDebtCurrent": ("Short-term debt", ("USD",)),
    "ShortTermBorrowingsAndCurrentMaturitiesOfLongTermDebt": ("Short-term debt", ("USD",)),
    "LongTermDebtNoncurrent": ("Long-term debt", ("USD",)),
    "LongTermDebt": ("Long-term debt", ("USD",)),
    "StockholdersEquity": ("Stockholders' equity", ("USD",)),
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": ("Stockholders' equity", ("USD",)),
    "RetainedEarningsAccumulatedDeficit": ("Retained earnings", ("USD",)),
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
