import math
import unittest
from datetime import date, timedelta

from scripts.forecast.pipeline import return_bundle, target_log_return


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


if __name__ == "__main__":
    unittest.main()
