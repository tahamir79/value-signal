import math
import unittest
from datetime import date, timedelta
from scripts.features import calculate_raw_features, normalize_universe
from scripts.models import FinancialFact, PriceBar

def bar(index: int, close: float) -> PriceBar:
    return PriceBar("TEST", (date(2025, 1, 1) + timedelta(days=index)).isoformat(), close, close, close, close, 100, "fixture", close)

def fact(label: str, value: float, year: int, concept: str = "Test") -> FinancialFact:
    return FinancialFact(concept, label, value, "USD", f"{year}-12-31", f"{year + 1}-02-01", year, "FY", "10-K", str(year))

class FeatureTests(unittest.TestCase):
    def test_returns_volatility_and_drawdown_use_ordered_history(self):
        prices = [bar(index, 100 + index) for index in range(100)]
        raw = calculate_raw_features(prices, [])
        self.assertAlmostEqual(raw["return_30d"], 199 / 169 - 1, places=7)
        self.assertAlmostEqual(raw["return_90d"], 199 / 109 - 1, places=7)
        self.assertGreater(raw["annualized_volatility"], 0)
        self.assertEqual(raw["max_drawdown_1y"], 0)

    def test_fundamental_features_and_missingness(self):
        prices = [bar(index, 10) for index in range(100)]
        facts = [fact("Revenue", 100, 2024), fact("Revenue", 120, 2025), fact("Net income", 10, 2024), fact("Net income", 18, 2025)]
        raw = calculate_raw_features(prices, facts)
        self.assertAlmostEqual(raw["revenue_growth"], 0.2)
        self.assertAlmostEqual(raw["net_margin"], 0.15)
        self.assertAlmostEqual(raw["net_margin_trend"], 0.05)
        self.assertIsNone(raw["earnings_yield"])

    def test_percentiles_are_stable_and_nulls_remain_explicit(self):
        rows = [{"ticker":"A","raw":{"return_30d":0.1}}, {"ticker":"B","raw":{"return_30d":0.2}}, {"ticker":"C","raw":{"return_30d":None}}]
        normalized = normalize_universe(rows)
        self.assertEqual(normalized[0]["percentile"]["return_30d"], 0.0)
        self.assertEqual(normalized[1]["percentile"]["return_30d"], 1.0)
        self.assertIsNone(normalized[2]["percentile"]["return_30d"])
        self.assertTrue(normalized[2]["missing"]["return_30d"])
        self.assertTrue(all(math.isfinite(value) for row in normalized for value in row["percentile"].values() if value is not None))

if __name__ == "__main__": unittest.main()
