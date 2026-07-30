from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.refresh_public_batch import merge_refreshed_batch, select_refresh_rows


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def dashboard_row(ticker: str, price: float) -> dict:
    return {
        "security": {"ticker": ticker, "cik": ticker, "company_name": f"{ticker} Inc.", "exchange": "NASDAQ", "sector": "Tech"},
        "derived": {"latestPrice": price, "dailyChangePercent": 0, "marketCapBillions": 1},
        "dataStatus": {"companyFactsAvailable": True},
        "growthSpurt": None,
    }


def feature_row(ticker: str, value: float) -> dict:
    return {
        "ticker": ticker,
        "asOf": "2026-07-29",
        "raw": {
            "return_30d": value,
            "return_90d": value,
            "annualized_volatility": 0.2,
            "max_drawdown_1y": -0.1,
            "earnings_yield": value,
            "sales_yield": value,
            "liabilities_to_assets": 0.4,
            "revenue_growth": value,
            "net_margin": value,
            "net_margin_trend": value,
        },
        "balanceSheetScoring": None,
    }


class ScheduledBatchRefreshTests(unittest.TestCase):
    def test_select_refresh_rows_wraps_and_advances_state(self) -> None:
        rows = [{"ticker": ticker, "cik": str(index), "isSupported": True} for index, ticker in enumerate(["A", "B", "C", "D"], 1)]
        selected, state = select_refresh_rows(rows, {"nextOffset": 3}, batch_size=2, batch_count=1)
        self.assertEqual([row["ticker"] for row in selected], ["D", "A"])
        self.assertEqual(state["previousOffset"], 3)
        self.assertEqual(state["nextOffset"], 1)

    def test_select_refresh_rows_records_daily_sweep_capacity(self) -> None:
        rows = [{"ticker": ticker, "cik": str(index), "isSupported": True} for index, ticker in enumerate(["A", "B", "C", "D", "E"], 1)]
        selected, state = select_refresh_rows(rows, {}, batch_size=2, batch_count=2, daily_sweep_slots=4)
        self.assertEqual([row["ticker"] for row in selected], ["A", "B", "C", "D"])
        self.assertEqual(state["batchSize"], 2)
        self.assertEqual(state["batchCount"], 2)
        self.assertEqual(state["dailySweepSlots"], 4)
        self.assertEqual(state["plannedDailyRefreshTickers"], 5)

    def test_merge_refreshed_batch_preserves_full_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public_data = root / "public" / "data"
            batch_output = root / "batch"
            write_json(public_data / "dashboard.json", {"schemaVersion": "1.0.0", "generatedAt": "old", "mode": "live", "records": [dashboard_row("A", 10), dashboard_row("B", 20)]})
            write_json(public_data / "features.json", {"schemaVersion": "1.0.0", "generatedAt": "old", "universeSize": 2, "records": [feature_row("A", 0.1), feature_row("B", 0.2)]})
            write_json(public_data / "signals.json", {"schemaVersion": "1.0.0", "generatedAt": "old", "universeSize": 2, "records": []})
            write_json(public_data / "etl_report.json", {"schemaVersion": "1.0.0"})
            write_json(public_data / "universe_coverage_report.json", {"schemaVersion": "1.0.0", "counts": {}})
            write_json(batch_output / "dashboard.json", {"records": [dashboard_row("B", 25)]})
            write_json(batch_output / "features.json", {"records": [feature_row("B", 0.3)]})
            write_json(batch_output / "stocks" / "B.json", {"record": dashboard_row("B", 25)})

            audit = merge_refreshed_batch(
                public_data=public_data,
                batch_output=batch_output,
                state={"selectedTickers": ["B"]},
                batch_audit={"runStartedAt": "start", "requestedTickers": 1, "successfulTickers": 1, "failedTickers": 0},
            )

            dashboard = json.loads((public_data / "dashboard.json").read_text(encoding="utf-8"))
            features = json.loads((public_data / "features.json").read_text(encoding="utf-8"))
            signals = json.loads((public_data / "signals.json").read_text(encoding="utf-8"))
            self.assertEqual([row["security"]["ticker"] for row in dashboard["records"]], ["A", "B"])
            self.assertEqual(dashboard["records"][1]["derived"]["latestPrice"], 25)
            self.assertEqual(features["universeSize"], 2)
            self.assertEqual(signals["universeSize"], 2)
            self.assertEqual(audit["fullUniversePublishedTickers"], 2)
            self.assertTrue((public_data / "stocks" / "B.json").exists())


if __name__ == "__main__":
    unittest.main()
