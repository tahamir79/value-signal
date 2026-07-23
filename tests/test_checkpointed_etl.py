import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.models import PriceBar
from scripts.pipeline.run_checkpointed_etl import (
    checkpoint_summary,
    fetch_checkpoints,
    merge_checkpoints,
)
from scripts.providers.price_provider import FixturePriceProvider
from scripts.providers.sec_companyfacts import FixtureCompanyFactsProvider


def price_series(ticker: str, start_price: float = 100.0, count: int = 130) -> list[PriceBar]:
    start = date(2025, 1, 1)
    rows = []
    for index in range(count):
        close = start_price + index
        rows.append(
            PriceBar(
                ticker,
                (start + timedelta(days=index)).isoformat(),
                close,
                close,
                close,
                close,
                1000,
                "fixture",
                close,
            )
        )
    return rows


def company_facts(asset_value: int = 1000) -> dict:
    return {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "val": asset_value,
                                "end": "2025-12-31",
                                "filed": "2026-02-01",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "accn": "x",
                            }
                        ]
                    }
                }
            }
        }
    }


class CheckpointedEtlTests(unittest.TestCase):
    def test_fetch_checkpoints_cache_and_global_merge(self):
        universe_payload = {
            "records": [
                {
                    "ticker": "AAPL",
                    "cik": "320193",
                    "companyName": "Apple Inc.",
                    "exchange": "NASDAQ",
                    "sector": "Technology",
                    "isSupported": True,
                },
                {
                    "ticker": "MSFT",
                    "cik": "789019",
                    "companyName": "Microsoft Corp.",
                    "exchange": "NASDAQ",
                    "sector": "Technology",
                    "isSupported": True,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            universe = root / "universe.json"
            checkpoint_dir = root / "checkpoints"
            output_dir = root / "public_data"
            universe.write_text(json.dumps(universe_payload), encoding="utf-8")

            summary = fetch_checkpoints(
                universe_path=universe,
                checkpoint_dir=checkpoint_dir,
                limit=None,
                offset=0,
                batch_size=1,
                max_batches=None,
                force=False,
                price_provider=FixturePriceProvider(
                    {
                        "SPY": price_series("SPY", 400),
                        "AAPL": price_series("AAPL", 100),
                        "MSFT": price_series("MSFT", 200),
                    }
                ),
                facts_provider=FixtureCompanyFactsProvider(
                    {
                        "0000320193": company_facts(1000),
                        "0000789019": company_facts(2000),
                    }
                ),
                progress=False,
                max_workers=2,
            )
            self.assertEqual(summary["batchesRun"], 2)
            self.assertFalse(summary["batches"][0]["cacheHit"])

            cached = fetch_checkpoints(
                universe_path=universe,
                checkpoint_dir=checkpoint_dir,
                limit=None,
                offset=0,
                batch_size=1,
                max_batches=None,
                force=False,
                price_provider=FixturePriceProvider({}),
                facts_provider=FixtureCompanyFactsProvider({}),
                progress=False,
                max_workers=2,
            )
            self.assertTrue(cached["benchmarkCacheHit"])
            self.assertTrue(all(batch["cacheHit"] for batch in cached["batches"]))

            raw_summary = checkpoint_summary(checkpoint_dir, selected_count=2, batch_size=1)
            self.assertTrue(raw_summary["complete"])
            self.assertEqual(raw_summary["completedBatches"], 2)

            audit = merge_checkpoints(
                universe_path=universe,
                checkpoint_dir=checkpoint_dir,
                output_dir=output_dir,
                limit=None,
                offset=0,
                batch_size=1,
                include_backtest=False,
            )
            self.assertEqual(audit["successfulTickers"], 2)
            self.assertEqual(audit["rawCheckpointSummary"]["successfulTickersInCheckpoints"], 2)
            published_audit = json.loads((output_dir / "etl_report.json").read_text(encoding="utf-8"))
            self.assertIn("rawCheckpointSummary", published_audit)

    def test_merge_blocks_when_expected_batch_is_missing(self):
        universe_payload = {
            "records": [
                {"ticker": "AAPL", "cik": "320193", "companyName": "Apple Inc.", "exchange": "NASDAQ", "isSupported": True},
                {"ticker": "MSFT", "cik": "789019", "companyName": "Microsoft Corp.", "exchange": "NASDAQ", "isSupported": True},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            universe = root / "universe.json"
            universe.write_text(json.dumps(universe_payload), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                merge_checkpoints(
                    universe_path=universe,
                    checkpoint_dir=root / "missing_checkpoints",
                    output_dir=root / "public_data",
                    limit=None,
                    offset=0,
                    batch_size=1,
                    include_backtest=False,
                )


if __name__ == "__main__":
    unittest.main()
