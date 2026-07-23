from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.build_search_index import build_index
from scripts.build_search_index_batch import attempted_tickers, empty_manifest, finalize_manifest, merge_ticker_index, select_batch
from scripts.models import Security


def security(ticker: str) -> Security:
    return Security(ticker, "0000000001", f"{ticker} Corp", "NYSE", "Unknown")


class SearchIndexBatchTests(unittest.TestCase):
    def test_select_batch_skips_already_indexed_tickers(self) -> None:
        manifest = empty_manifest()
        manifest["tickers"] = {"AAPL": {"documentCount": 3, "path": "public/data/search/AAPL.json"}}
        selected = select_batch(
            [security("AAPL"), security("MSFT"), security("GOOGL")],
            manifest,
            batch_size=2,
        )
        self.assertEqual([item.ticker for item in selected], ["MSFT", "GOOGL"])

    def test_select_batch_skips_failed_attempts_without_force(self) -> None:
        manifest = empty_manifest()
        manifest["errors"] = [{"ticker": "AAC", "message": "NO_SEARCHABLE_FILING_CHUNKS"}]
        selected = select_batch(
            [security("AAC"), security("AAPL"), security("MSFT")],
            manifest,
            batch_size=2,
        )
        self.assertEqual([item.ticker for item in selected], ["AAPL", "MSFT"])
        forced = select_batch(
            [security("AAC"), security("AAPL"), security("MSFT")],
            manifest,
            batch_size=2,
            force=True,
        )
        self.assertEqual([item.ticker for item in forced], ["AAC", "AAPL"])
        self.assertIn("AAC", attempted_tickers(manifest))

    def test_batch_index_uses_fixed_universe_window_before_missing_filter(self) -> None:
        manifest = empty_manifest()
        manifest["tickers"] = {"AAPL": {"documentCount": 3, "path": "public/data/search/AAPL.json"}}
        selected = select_batch(
            [security("AAPL"), security("MSFT"), security("GOOGL")],
            manifest,
            batch_size=2,
            batch_index=0,
        )
        self.assertEqual([item.ticker for item in selected], ["MSFT"])

    def test_merge_ticker_index_uses_safe_reserved_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = empty_manifest()
            index = build_index([{
                "ticker": "CON",
                "id": "con-risk",
                "chunkId": "con-risk",
                "accession": "0000000001-26-000001",
                "filingDate": "2026-01-01",
                "reportDate": "2025-12-31",
                "form": "10-K",
                "item": "Item 1A",
                "url": "https://www.sec.gov/example",
                "text": "Liquidity and supply chain risk may affect operations.",
            }])
            merge_ticker_index(manifest, ticker="CON", ticker_index=index, search_dir=root / "search")
            finalize_manifest(manifest, batch={"finished": True}, errors=[])
            self.assertIn("CON", manifest["tickers"])
            self.assertTrue(manifest["tickers"]["CON"]["path"].endswith("/_CON.json"))
            self.assertTrue((root / "search" / "_CON.json").exists())
            self.assertEqual(manifest["documentCount"], 1)


if __name__ == "__main__":
    unittest.main()
