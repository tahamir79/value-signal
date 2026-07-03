from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from scripts.providers.http import fetch_json

class CompanyFactsProvider(ABC):
    @abstractmethod
    def fetch(self, cik: str) -> dict[str, Any]: ...

class SecCompanyFactsProvider(CompanyFactsProvider):
    base_url = "https://data.sec.gov/api/xbrl/companyfacts"
    def __init__(self, user_agent: str) -> None: self.user_agent = user_agent
    def fetch(self, cik: str) -> dict[str, Any]:
        return fetch_json(f"{self.base_url}/CIK{cik.zfill(10)}.json", self.user_agent)

class FixtureCompanyFactsProvider(CompanyFactsProvider):
    def __init__(self, records: dict[str, dict[str, Any]]) -> None: self.records = records
    def fetch(self, cik: str) -> dict[str, Any]: return self.records[cik.zfill(10)]
