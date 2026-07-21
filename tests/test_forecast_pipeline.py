import math
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.forecast import pipeline as forecast_pipeline
from scripts.forecast.pipeline import conservative_scenario, quantile, return_bundle, target_log_return


class ForecastPipelineTests(unittest.TestCase):
    def test_calendar_day_target_uses_first_session_on_or_after_horizon(self):
        prices = [
            {"date": "2026-01-02", "adjusted_close": 100.0, "close": 100.0},
            {"date": "2026-01-30", "adjusted_close": 120.0, "close": 120.0},
            {"date": "2026-02-02", "adjusted_close": 121.0, "close": 121.0},
        ]
        expected = math.log(121.0 / 100.0)
        self.assertAlmostEqual(target_log_return(prices, 0, 30), expected)

    def test_return_bundle_keeps_zero_prediction_available(self):
        bundle = return_bundle(50.0, 0.0, -0.10, 0.15)
        self.assertEqual(bundle["returnEstimate"], 0.0)
        self.assertEqual(bundle["estimatedPrice"], 50.0)
        self.assertLess(bundle["lowerReturn"], bundle["returnEstimate"])
        self.assertGreater(bundle["upperReturn"], bundle["returnEstimate"])

    def test_return_bundle_rejects_below_negative_100_percent(self):
        bundle = return_bundle(100.0, -100.0, -10.0, 0.0)
        self.assertGreater(bundle["lowerReturn"], -1.0)
        self.assertLessEqual(bundle["lowerReturn"], bundle["returnEstimate"])
        self.assertLessEqual(bundle["returnEstimate"], bundle["upperReturn"])

    def test_conservative_scenario_uses_sparse_samples_shrinkage_and_caps(self):
        rows = []
        start = date(2024, 1, 2)
        for index in range(700):
            rows.append({
                "ticker": "TEST",
                "featureDate": (start + timedelta(days=index)).isoformat(),
                "currentAdjustedClose": 100 + index,
                "targetLogReturn30": math.log(1.20),
                "targetLogReturn90": math.log(0.90),
            })
        scenario = conservative_scenario(rows, rows[-1], "2025-12-05T00:00:00+00:00")
        self.assertEqual(scenario["methodology"], "valuesignal_conservative_historical_scenario_v1")
        self.assertEqual(scenario["status"], "available")
        self.assertEqual(scenario["horizon30Day"]["returnEstimate"], 0.08)
        self.assertLessEqual(scenario["horizon30Day"]["lowerReturn"], scenario["horizon30Day"]["returnEstimate"])
        self.assertLessEqual(scenario["horizon30Day"]["returnEstimate"], scenario["horizon30Day"]["upperReturn"])
        self.assertGreaterEqual(scenario["horizon90Day"]["returnEstimate"], -0.15)
        self.assertGreaterEqual(scenario["horizon30Day"]["sampleCount"], 24)
        self.assertGreaterEqual(scenario["horizon90Day"]["sampleCount"], 12)

    def test_conservative_scenario_marks_insufficient_history(self):
        rows = [{
            "ticker": "TEST",
            "featureDate": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "currentAdjustedClose": 100.0,
            "targetLogReturn30": math.log(1.01),
            "targetLogReturn90": math.log(1.02),
        } for index in range(40)]
        scenario = conservative_scenario(rows, rows[-1], "2026-02-10T00:00:00+00:00")
        self.assertEqual(scenario["status"], "insufficient_data")
        self.assertIsNone(scenario["horizon30Day"]["returnEstimate"])

    def test_quantile_is_deterministic(self):
        self.assertEqual(quantile([3, 1, 2], 0.5), 2)
        self.assertAlmostEqual(quantile([0, 10], 0.25), 2.5)

    def test_stock_roster_and_forecast_cleanup_follow_current_summary(self):
        original_stock_dir = forecast_pipeline.STOCK_DIR
        original_forecast_dir = forecast_pipeline.FORECAST_DIR
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stock_dir = root / "stocks"
            forecast_dir = root / "forecasts"
            stock_dir.mkdir()
            forecast_dir.mkdir()
            (stock_dir / "summary.json").write_text('{"records":[{"ticker":"AAPL"},{"ticker":"MSFT"}]}', encoding="utf-8")
            for ticker in ("AAPL", "MSFT", "OLD"):
                (stock_dir / f"{ticker}.json").write_text("{}", encoding="utf-8")
            for ticker in ("AAPL", "OLD"):
                (forecast_dir / f"{ticker}.json").write_text("{}", encoding="utf-8")
            (forecast_dir / "summary.json").write_text("{}", encoding="utf-8")
            try:
                forecast_pipeline.STOCK_DIR = stock_dir
                forecast_pipeline.FORECAST_DIR = forecast_dir
                self.assertEqual([path.stem for path in forecast_pipeline.stock_files()], ["AAPL", "MSFT"])
                removed = forecast_pipeline.remove_stale_forecast_artifacts({"AAPL"})
                self.assertEqual(removed, ["OLD"])
                self.assertTrue((forecast_dir / "summary.json").exists())
                self.assertTrue((forecast_dir / "AAPL.json").exists())
                self.assertFalse((forecast_dir / "OLD.json").exists())
            finally:
                forecast_pipeline.STOCK_DIR = original_stock_dir
                forecast_pipeline.FORECAST_DIR = original_forecast_dir


if __name__ == "__main__":
    unittest.main()
