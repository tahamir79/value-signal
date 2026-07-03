from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

@dataclass(frozen=True)
class Security:
    ticker: str
    cik: str
    company_name: str
    exchange: str
    sector: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.upper().strip())
        object.__setattr__(self, "cik", self.cik.zfill(10))
        if not self.ticker or not self.cik.isdigit() or len(self.cik) != 10:
            raise ValueError("Security requires a ticker and ten-digit CIK")

@dataclass(frozen=True)
class PriceBar:
    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str
    adjusted_close: float | None = None

@dataclass(frozen=True)
class FinancialFact:
    concept: str
    label: str
    value: float
    unit: str
    period_end: str
    filed: str
    fiscal_year: int | None
    fiscal_period: str | None
    form: str
    accession: str
    source: str = "sec-companyfacts"

def record(value: Any) -> dict[str, Any]:
    return asdict(value)
