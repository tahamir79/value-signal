import unittest
from datetime import date, timedelta

from scripts.benchmark_growth_spurt import evaluate_growth_spurt_history
from scripts.growth_spurt import (
    apply_growth_spurt_percentiles,
    calculate_growth_spurt,
    normalize_price_points,
)
from scripts.models import PriceBar


def bars(ticker: str, values: list[float | None], *, adjusted: list[float | None] | None = None) -> list[PriceBar]:
    start = date(2025, 1, 1)
    rows = []
    for index, value in enumerate(values):
        if value is None:
            rows.append(PriceBar(ticker, (start + timedelta(days=index)).isoformat(), 0, 0, 0, 0, 100, "fixture", None))
            continue
        adjusted_close = adjusted[index] if adjusted is not None else value
        rows.append(PriceBar(ticker, (start + timedelta(days=index)).isoformat(), value, value, value, value, 100, "fixture", adjusted_close))
    return rows


class GrowthSpurtCalculationTests(unittest.TestCase):
    def test_chronological_sorting_adjusted_close_preference_duplicates_and_missing_prices(self):
        rows = [
            {"date": "2025-01-03", "close": 30, "adjusted_close": 29},
            {"date": "2025-01-01", "close": 10, "adjusted_close": 11},
            {"date": "2025-01-02", "close": 20, "adjusted_close": None},
            {"date": "2025-01-02", "close": 21, "adjusted_close": 22},
            {"date": "2025-01-04", "close": None, "adjusted_close": None},
        ]
        normalized = normalize_price_points(rows)
        self.assertEqual([point.date for point in normalized], ["2025-01-01", "2025-01-02", "2025-01-03"])
        self.assertEqual([point.price for point in normalized], [11.0, 22.0, 29.0])

    def test_smooth_upward_path_is_detected(self):
        stock = [100 * (1.003 ** index) for index in range(130)]
        spy = [100 * (1.001 ** index) for index in range(130)]
        artifact = calculate_growth_spurt("TEST", bars("TEST", stock), bars("SPY", spy), generated_at="2026-01-01T00:00:00+00:00")
        self.assertEqual(artifact["status"], "detected")
        self.assertGreaterEqual(artifact["growthSpurtScore"], 70)
        self.assertIn("GROWTH_SPURT_DETECTED", artifact["reasonCodes"])
        self.assertGreater(artifact["metrics"]["excessReturnVsSpy63d"], 0)

    def test_flat_and_falling_paths_do_not_detect(self):
        spy = bars("SPY", [100] * 130)
        flat = calculate_growth_spurt("FLAT", bars("FLAT", [100] * 130), spy)
        falling = calculate_growth_spurt("DOWN", bars("DOWN", [130 - index * 0.2 for index in range(130)]), spy)
        self.assertNotEqual(flat["status"], "detected")
        self.assertNotEqual(falling["status"], "detected")
        self.assertLessEqual(falling["scoreBreakdown"]["directionScore"], flat["scoreBreakdown"]["directionScore"])

    def test_one_day_spike_is_rejected(self):
        values = [100.0] * 130
        values[-40] = 150.0
        artifact = calculate_growth_spurt("SPIKE", bars("SPIKE", values), bars("SPY", [100.0] * 130))
        self.assertNotEqual(artifact["status"], "detected")
        self.assertIn("ONE_DAY_SPIKE_DOMINATED", artifact["warnings"])
        self.assertIn("ONE_DAY_SPIKE_DOMINATED", artifact["reasonCodes"])

    def test_noisy_zigzag_has_weak_consistency(self):
        values = [100 + index * 0.15 + (6 if index % 2 else -6) for index in range(130)]
        artifact = calculate_growth_spurt("NOISY", bars("NOISY", values), bars("SPY", [100.0] * 130))
        self.assertNotEqual(artifact["status"], "detected")
        self.assertLess(artifact["scoreBreakdown"]["consistencyScore"], 45)
        self.assertIn("TREND_TOO_VOLATILE", artifact["reasonCodes"])

    def test_positive_long_return_alone_is_insufficient(self):
        values = [70.0] * 35 + [100.0] * 95
        artifact = calculate_growth_spurt("STEP", bars("STEP", values), bars("SPY", [100.0] * 130))
        self.assertNotEqual(artifact["status"], "detected")
        self.assertEqual(artifact["metrics"]["return63d"], 0.0)

    def test_negative_21_day_confirmation_weakens_detection(self):
        values = [100 * (1.004 ** index) for index in range(109)]
        last = values[-1]
        values.extend([last * (0.996 ** index) for index in range(1, 22)])
        artifact = calculate_growth_spurt("ROLL", bars("ROLL", values), bars("SPY", [100.0] * len(values)))
        self.assertNotEqual(artifact["status"], "detected")
        self.assertLess(artifact["metrics"]["return21d"], 0)

    def test_strong_market_rise_without_stock_outperformance_reduces_relative_score(self):
        stock = [100 * (1.0015 ** index) for index in range(130)]
        spy = [100 * (1.004 ** index) for index in range(130)]
        artifact = calculate_growth_spurt("MARKET", bars("MARKET", stock), bars("SPY", spy))
        self.assertLess(artifact["scoreBreakdown"]["relativeStrengthScore"], 50)
        self.assertIn("TREND_WEAK_RELATIVE_TO_MARKET", artifact["reasonCodes"])

    def test_insufficient_history_is_unavailable_not_zero(self):
        artifact = calculate_growth_spurt("SHORT", bars("SHORT", [100.0] * 20), bars("SPY", [100.0] * 130))
        self.assertEqual(artifact["status"], "unavailable")
        self.assertIsNone(artifact["growthSpurtScore"])
        self.assertIn("TREND_HISTORY_INSUFFICIENT", artifact["warnings"])

    def test_cross_sectional_percentiles_preserve_raw_metrics(self):
        spy = bars("SPY", [100 * (1.001 ** index) for index in range(130)])
        slow = calculate_growth_spurt("SLOW", bars("SLOW", [100 * (1.0012 ** index) for index in range(130)]), spy)
        fast = calculate_growth_spurt("FAST", bars("FAST", [100 * (1.003 ** index) for index in range(130)]), spy)
        apply_growth_spurt_percentiles([slow, fast])
        self.assertGreater(fast["benchmarkPercentile"], slow["benchmarkPercentile"])
        self.assertGreater(fast["metricPercentiles"]["trendSlope63d"], slow["metricPercentiles"]["trendSlope63d"])
        self.assertGreater(fast["metrics"]["trendSlope63d"], slow["metrics"]["trendSlope63d"])


class GrowthSpurtBenchmarkTests(unittest.TestCase):
    def test_historical_benchmark_uses_point_in_time_snapshots_and_aligns_forward_return(self):
        stock_prices = [100 * (1.003 ** index) for index in range(170)]
        spy_prices = [100 * (1.001 ** index) for index in range(170)]
        payload = {"security": {"ticker": "TEST", "sector": "Technology"}, "priceHistory": [bar.__dict__ for bar in bars("TEST", stock_prices)]}
        report = evaluate_growth_spurt_history([payload], [bar.__dict__ for bar in bars("SPY", spy_prices)], horizons=(21,), snapshot_frequency_sessions=200, generated_at="2026-01-01T00:00:00+00:00")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["sampleSize"]["candidateSnapshots"], 1)
        self.assertEqual(report["sampleSize"]["forwardObservations"], 1)
        observation = report["observationsPreview"][0]
        self.assertLess(observation["detectorPriceCount"], observation["priceHistoryLengthAtTickerEnd"])
        self.assertLess(observation["signalDate"], observation["entryDate"])
        self.assertLess(observation["entryDate"], observation["exitDate"])
        self.assertAlmostEqual(observation["forwardReturn"], 1.003 ** 21 - 1, places=7)
        self.assertAlmostEqual(observation["spyReturn"], 1.001 ** 21 - 1, places=7)
        self.assertTrue(report["holdoutPolicy"]["finalHoldoutPeriodUntouched"])

    def test_benchmark_records_false_positives(self):
        pre_signal = [100 * (1.003 ** index) for index in range(128)]
        post_signal = [pre_signal[-1] * (0.99 ** index) for index in range(1, 43)]
        stock_prices = pre_signal + post_signal
        spy_prices = [100.0] * len(stock_prices)
        payload = {"security": {"ticker": "DROP", "sector": "Energy"}, "priceHistory": [bar.__dict__ for bar in bars("DROP", stock_prices)]}
        report = evaluate_growth_spurt_history([payload], [bar.__dict__ for bar in bars("SPY", spy_prices)], horizons=(21,), snapshot_frequency_sessions=200)
        self.assertEqual(report["sampleSize"]["forwardObservations"], 1)
        self.assertEqual(report["summaryByHorizon"]["21"]["falsePositiveCount"], 1)
        self.assertEqual(report["bySector"]["Energy"]["sampleCount"], 1)


if __name__ == "__main__":
    unittest.main()
