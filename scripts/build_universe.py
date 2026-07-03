from __future__ import annotations
from scripts.models import Security

UNIVERSE = (
    Security("AAPL", "320193", "Apple Inc.", "NASDAQ", "Technology"),
    Security("MSFT", "789019", "Microsoft Corp.", "NASDAQ", "Technology"),
    Security("GOOGL", "1652044", "Alphabet Inc.", "NASDAQ", "Communication Services"),
    Security("AMZN", "1018724", "Amazon.com Inc.", "NASDAQ", "Consumer Discretionary"),
    Security("JPM", "19617", "JPMorgan Chase & Co.", "NYSE", "Financials"),
    Security("JNJ", "200406", "Johnson & Johnson", "NYSE", "Health Care"),
    Security("XOM", "34088", "Exxon Mobil Corp.", "NYSE", "Energy"),
    Security("F", "37996", "Ford Motor Co.", "NYSE", "Consumer Discretionary"),
    Security("KO", "21344", "The Coca-Cola Co.", "NYSE", "Consumer Staples"),
    Security("INTC", "50863", "Intel Corp.", "NASDAQ", "Technology"),
)

def build_universe(limit: int | None = None) -> list[Security]:
    records = list(UNIVERSE[:limit] if limit else UNIVERSE)
    if len({item.ticker for item in records}) != len(records):
        raise ValueError("Universe contains duplicate tickers")
    return records
