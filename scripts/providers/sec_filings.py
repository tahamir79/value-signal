from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.providers.http import fetch_bytes, fetch_json


@dataclass(frozen=True)
class FilingDocument:
    ticker: str
    cik: str
    accession: str
    filing_date: str
    report_date: str
    form: str
    primary_document: str
    url: str
    html: str


class SecFilingProvider:
    submissions_url = "https://data.sec.gov/submissions"
    archives_url = "https://www.sec.gov/Archives/edgar/data"

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def recent_metadata(self, cik: str, forms: tuple[str, ...] = ("10-K", "10-Q"), per_form: int = 1) -> list[dict[str, Any]]:
        payload = fetch_json(f"{self.submissions_url}/CIK{cik.zfill(10)}.json", self.user_agent)
        recent = payload.get("filings", {}).get("recent", {})
        rows = []
        counts = {form: 0 for form in forms}
        for index, form in enumerate(recent.get("form", [])):
            if form not in counts or counts[form] >= per_form:
                continue
            try:
                row = {name: recent.get(name, [])[index] for name in ("accessionNumber", "filingDate", "reportDate", "form", "primaryDocument")}
            except IndexError:
                continue
            if not row["accessionNumber"] or not row["primaryDocument"]:
                continue
            counts[form] += 1
            rows.append(row)
        return rows

    def fetch_recent(self, ticker: str, cik: str, per_form: int = 1) -> list[FilingDocument]:
        documents = []
        for row in self.recent_metadata(cik, per_form=per_form):
            accession_path = row["accessionNumber"].replace("-", "")
            url = f"{self.archives_url}/{int(cik)}/{accession_path}/{row['primaryDocument']}"
            html = fetch_bytes(url, self.user_agent).decode("utf-8", errors="replace")
            documents.append(FilingDocument(ticker, cik.zfill(10), row["accessionNumber"], row["filingDate"], row["reportDate"], row["form"], row["primaryDocument"], url, html))
        return documents
