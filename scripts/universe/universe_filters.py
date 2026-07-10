from __future__ import annotations

import re
from dataclasses import dataclass


SUPPORTED_EXCHANGES = {"NYSE", "NASDAQ", "NYSE AMERICAN"}
UNSUPPORTED_NAME_PATTERNS = (
    r"\bETF\b", r"\bETN\b", r"\bFUND\b", r"\bTRUST\b", r"\bSPAC\b",
    r"\bWARRANT", r"\bRIGHTS?\b", r"\bUNIT\b", r"\bPREFERRED\b",
)
UNSUPPORTED_TICKER_PATTERNS = (r"-W$", r"-WS$", r"-WT$", r"-R$", r"-U$", r"-P[A-Z]?$")


@dataclass(frozen=True)
class SupportDecision:
    is_supported: bool
    support_reason: str | None = None
    exclude_reason: str | None = None
    priority: int = 100


def classify_security(ticker: str, company_name: str, exchange: str | None) -> SupportDecision:
    name = company_name.upper()
    normalized_exchange = (exchange or "").upper()
    for pattern in UNSUPPORTED_TICKER_PATTERNS:
        if re.search(pattern, ticker):
            return SupportDecision(False, exclude_reason="unsupported ticker suffix", priority=900)
    for pattern in UNSUPPORTED_NAME_PATTERNS:
        if re.search(pattern, name):
            return SupportDecision(False, exclude_reason="likely fund/trust/unit/warrant security", priority=900)
    if normalized_exchange and normalized_exchange not in SUPPORTED_EXCHANGES:
        return SupportDecision(False, exclude_reason=f"exchange not in default core set: {exchange}", priority=700)
    return SupportDecision(True, support_reason="NYSE/Nasdaq operating-company candidate", priority=100)

