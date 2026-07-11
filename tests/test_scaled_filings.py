from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.filings.ingest_filings import IngestPaths, discover_filings, filing_metadata, filter_universe, ingest_company
from scripts.sec.sec_client import SecClient


SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-K", "8-K", "10-Q", "10-Q"],
            "filingDate": ["2025-10-31", "2025-09-01", "2025-07-31", "2025-04-30"],
            "reportDate": ["2025-09-30", "2025-08-29", "2025-06-30", "2025-03-31"],
            "accessionNumber": ["0000320193-25-000001", "0000320193-25-000002", "0000320193-25-000003", "0000320193-25-000004"],
            "primaryDocument": ["aapl-20250930.htm", "aapl-8k.htm", "aapl-20250630.htm", "aapl-20250331.htm"],
        }
    }
}

HTML = """
<html><body>
<p>Part I</p>
<p>Item 1. Business</p>
<p>Apple sells products and services to customers around the world. This business section has enough
detail to support chunking for a scaled ingestion smoke test. The company discusses products, services,
customers, distribution, and operational dependencies in a concise but substantive paragraph.</p>
<p>Item 1A. Risk Factors</p>
<p>Risk factors include competition, supply constraints, macroeconomic pressure, cybersecurity incidents,
and changes in consumer demand. These risks may affect revenue, margins, cash flow, operating results,
or the timing of product launches. Management cannot guarantee that mitigation efforts will avoid harm.</p>
<p>Part II</p>
<p>Item 7. Management Discussion and Analysis</p>
<p>Results of operations may change because revenue growth, margin pressure, foreign exchange, and
component costs can vary by period. Liquidity depends on cash generation, capital allocation, and market
conditions.</p>
<p>Signatures</p>
</body></html>
"""


class FakeClient(SecClient):
    def __init__(self, tmp: str) -> None:
        super().__init__(user_agent="ValueSignal test@example.com", cache_dir=tmp)

    def get_json(self, url: str, *, force: bool = False):
        return SUBMISSIONS, {"url": url, "status": 200, "cacheHit": False}

    def get_bytes(self, url: str, *, force: bool = False):
        return HTML.encode("utf-8"), {"url": url, "status": 200, "cacheHit": False}


class ScaledFilingTests(unittest.TestCase):
    def test_discover_filings_respects_forms_per_form_and_since(self) -> None:
        rows = discover_filings(SUBMISSIONS, forms=["10-K", "10-Q"], per_form=1, since="2025-01-01")
        self.assertEqual([row["formType"] for row in rows], ["10-K", "10-Q"])
        self.assertEqual(rows[0]["accession"], "0000320193-25-000001")

    def test_filter_universe_uses_supported_ticker_limit(self) -> None:
        rows = [
            {"ticker": "AAPL", "isSupported": True},
            {"ticker": "ETF", "isSupported": False},
            {"ticker": "MSFT", "isSupported": True},
        ]
        self.assertEqual([row["ticker"] for row in filter_universe(rows, limit=2)], ["AAPL", "MSFT"])
        self.assertEqual([row["ticker"] for row in filter_universe(rows, ticker="msft")], ["MSFT"])

    def test_filing_metadata_paths_are_per_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = IngestPaths(Path(tmp))
            meta = filing_metadata({"cik": "320193", "ticker": "aapl", "companyName": "Apple Inc."},
                                   discover_filings(SUBMISSIONS, forms=["10-K"], per_form=1)[0], paths)
            self.assertEqual(meta["cik"], "0000320193")
            self.assertIn("000032019325000001", meta["documentUrl"])
            self.assertTrue(meta["localRawPath"].endswith(".html"))

    def test_ingest_company_writes_clean_text_and_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = IngestPaths(Path(tmp))
            metadata, chunks, failures = ingest_company(
                {"cik": "320193", "ticker": "AAPL", "companyName": "Apple Inc."},
                client=FakeClient(tmp),
                paths=paths,
                forms=["10-K"],
                per_form=1,
                since=None,
                force=False,
                dry_run=False,
            )
            self.assertFalse(failures)
            self.assertEqual(metadata[0]["status"], "chunked")
            self.assertTrue(Path(metadata[0]["localCleanPath"]).exists())
            self.assertTrue(Path(metadata[0]["localChunkPath"]).exists())
            self.assertTrue(chunks)
            self.assertTrue(all(chunk["ticker"] == "AAPL" for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
