from __future__ import annotations
from scripts.models import FinancialFact, PriceBar

def derive_fields(prices: list[PriceBar], facts: dict[str, FinancialFact]) -> dict[str, float | None]:
    latest = prices[-1]
    prior = prices[-2] if len(prices) > 1 else None
    change = ((latest.close / prior.close) - 1) * 100 if prior and prior.close else None
    shares = facts.get("Shares outstanding")
    assets = facts.get("Assets")
    liabilities = facts.get("Liabilities")
    return {
        "latestPrice": round(latest.close, 4),
        "dailyChangePercent": round(change, 4) if change is not None else None,
        "marketCapBillions": round(latest.close * shares.value / 1_000_000_000, 4) if shares else None,
        "liabilitiesToAssets": round(liabilities.value / assets.value, 6) if assets and liabilities and assets.value else None,
    }
