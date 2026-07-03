from __future__ import annotations
import csv
import io
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from datetime import date, timedelta
from scripts.models import PriceBar
from scripts.providers.http import ProviderError, fetch_bytes
from scripts.providers.http import fetch_json

class PriceProvider(ABC):
    @abstractmethod
    def fetch(self, ticker: str) -> list[PriceBar]: ...

class StooqPriceProvider(PriceProvider):
    """Keyless daily-price adapter. Replace without changing the ETL runner."""
    name = "stooq"
    def __init__(self, user_agent: str, lookback_days: int = 400) -> None:
        self.user_agent = user_agent
        self.lookback_days = lookback_days

    def fetch(self, ticker: str) -> list[PriceBar]:
        end = date.today()
        start = end - timedelta(days=self.lookback_days)
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d"
        payload = fetch_bytes(url, self.user_agent).decode("utf-8-sig")
        rows: list[PriceBar] = []
        for item in csv.DictReader(io.StringIO(payload)):
            try:
                rows.append(PriceBar(ticker.upper(), item["Date"], float(item["Open"]), float(item["High"]), float(item["Low"]), float(item["Close"]), int(float(item["Volume"])), self.name))
            except (KeyError, TypeError, ValueError):
                continue
        if not rows:
            raise ProviderError(f"No valid price rows for {ticker}")
        return sorted(rows, key=lambda row: row.date)

class YahooChartPriceProvider(PriceProvider):
    """Keyless Yahoo chart adapter; isolated because it is not a contracted API."""
    name = "yahoo-chart"
    def __init__(self, user_agent: str, range_name: str = "1y") -> None:
        self.user_agent = user_agent
        self.range_name = range_name

    def fetch(self, ticker: str) -> list[PriceBar]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker.upper()}?range={self.range_name}&interval=1d&events=history"
        payload = fetch_json(url, self.user_agent)
        result = (payload.get("chart", {}).get("result") or [None])[0]
        if not result:
            error = payload.get("chart", {}).get("error")
            raise ProviderError(f"No chart result for {ticker}: {error}")
        timestamps = result.get("timestamp", [])
        quotes = (result.get("indicators", {}).get("quote") or [{}])[0]
        adjusted = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose", [])
        rows: list[PriceBar] = []
        for index, timestamp in enumerate(timestamps):
            try:
                values = {name: quotes.get(name, [])[index] for name in ("open", "high", "low", "close", "volume")}
                if any(value is None for value in values.values()):
                    continue
                adjusted_close = adjusted[index] if index < len(adjusted) else None
                rows.append(PriceBar(ticker.upper(), datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(), float(values["open"]), float(values["high"]), float(values["low"]), float(values["close"]), int(values["volume"]), self.name, float(adjusted_close) if adjusted_close is not None else None))
            except (IndexError, TypeError, ValueError):
                continue
        if not rows:
            raise ProviderError(f"No valid price rows for {ticker}")
        return sorted(rows, key=lambda row: row.date)

class FixturePriceProvider(PriceProvider):
    def __init__(self, records: dict[str, list[PriceBar]]) -> None: self.records = records
    def fetch(self, ticker: str) -> list[PriceBar]:
        if ticker not in self.records: raise ProviderError(f"Fixture missing {ticker}")
        return self.records[ticker]
