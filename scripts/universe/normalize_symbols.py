from __future__ import annotations

import re


def normalize_cik(value: int | str) -> str:
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        raise ValueError("CIK is required")
    return digits.zfill(10)


def normalize_ticker(value: str) -> str:
    ticker = str(value or "").strip().upper().replace(".", "-")
    if not ticker:
        raise ValueError("ticker is required")
    return ticker


def stable_universe_key(cik: int | str, ticker: str) -> str:
    return f"{normalize_cik(cik)}:{normalize_ticker(ticker)}"

