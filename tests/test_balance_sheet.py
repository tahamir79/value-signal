import os
import unittest

from scripts.balance_sheet import balance_sheet_bundle, experimental_signal
from scripts.models import FinancialFact, Security
from scripts.scoring import score_record


def fact(concept: str, label: str, value: float, accession: str = "accn") -> FinancialFact:
    return FinancialFact(concept, label, value, "USD", "2025-12-31", "2026-02-01", 2025, "FY", "10-K", accession)


class BalanceSheetScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.security = Security("TEST", "1", "Test Co", "NASDAQ", "Industrials")

    def test_ratio_calculation_and_healthy_bands(self) -> None:
        bundle = balance_sheet_bundle(self.security, [
            fact("Assets", "Assets", 1000),
            fact("AssetsCurrent", "Current assets", 300),
            fact("Cash", "Cash and equivalents", 150),
            fact("Receivables", "Accounts receivable", 80),
            fact("Liabilities", "Liabilities", 400),
            fact("LiabilitiesCurrent", "Current liabilities", 100),
            fact("DebtCurrent", "Short-term debt", 20),
            fact("DebtLong", "Long-term debt", 100),
            fact("Equity", "Stockholders' equity", 600),
            fact("Retained", "Retained earnings", 200),
        ], market_cap=1200, shares_outstanding=10)
        self.assertEqual(bundle["metrics"]["currentRatio"], 3)
        self.assertEqual(bundle["metrics"]["debtToAssets"], 0.12)
        statuses = {row["metric"]: row["status"] for row in bundle["scoring"]["targetComparisons"]}
        self.assertEqual(statuses["currentRatio"], "healthy")
        self.assertEqual(statuses["debtToAssets"], "healthy")
        self.assertGreaterEqual(bundle["scoring"]["balanceSheetQualityScore"], 70)

    def test_negative_equity_and_leverage_gate(self) -> None:
        bundle = balance_sheet_bundle(self.security, [
            fact("Assets", "Assets", 100),
            fact("AssetsCurrent", "Current assets", 20),
            fact("Cash", "Cash and equivalents", 1),
            fact("Liabilities", "Liabilities", 140),
            fact("LiabilitiesCurrent", "Current liabilities", 40),
            fact("DebtCurrent", "Short-term debt", 30),
            fact("DebtLong", "Long-term debt", 70),
            fact("Equity", "Stockholders' equity", -40),
        ])
        gates = {gate["name"] for gate in bundle["scoring"]["triggeredRiskGates"] if gate["triggered"]}
        self.assertIn("Negative Equity Gate", gates)
        self.assertIn("Severe Leverage Gate", gates)
        self.assertLessEqual(bundle["scoring"]["solvencyScore"], 15)
        self.assertGreaterEqual(bundle["scoring"]["balanceSheetRiskPenalty"], 70)

    def test_shadow_mode_does_not_change_official_signal(self) -> None:
        previous = os.environ.get("BALANCE_SHEET_SCORING_MODE")
        os.environ["BALANCE_SHEET_SCORING_MODE"] = "shadow"
        try:
            row = {
                "ticker": "TEST",
                "asOf": "2026-01-01",
                "raw": {"earnings_yield": 0.1, "sales_yield": 2, "liabilities_to_assets": 0.2, "return_90d": 0.1, "return_30d": 0.05, "annualized_volatility": 0.2, "max_drawdown_1y": -0.1, "revenue_growth": 0.1, "net_margin": 0.2, "net_margin_trend": 0.01},
                "percentile": {"earnings_yield": 0.9, "sales_yield": 0.9, "liabilities_to_assets": 0.1, "return_90d": 0.5, "return_30d": 0.5, "annualized_volatility": 0.1, "max_drawdown_1y": 0.9, "revenue_growth": 0.7, "net_margin": 0.7, "net_margin_trend": 0.7},
                "balanceSheetScoring": {"balanceSheetQualityScore": 10, "balanceSheetRiskPenalty": 95, "confidenceAdjustment": -10, "triggeredRiskGates": [{"name": "Severe Leverage Gate", "severity": "severe", "triggered": True}], "targetComparisons": [], "warnings": []},
            }
            scored = score_record(row)
            self.assertEqual(scored["signal"], "potentially-undervalued")
            self.assertIn("balanceSheetScoringShadow", scored)
            self.assertTrue(scored["balanceSheetScoringShadow"]["experimentalSignalImpact"]["wouldChangeSignal"])
        finally:
            if previous is None:
                os.environ.pop("BALANCE_SHEET_SCORING_MODE", None)
            else:
                os.environ["BALANCE_SHEET_SCORING_MODE"] = previous

    def test_official_mode_can_change_signal(self) -> None:
        previous = os.environ.get("BALANCE_SHEET_SCORING_MODE")
        os.environ["BALANCE_SHEET_SCORING_MODE"] = "official"
        try:
            row = {
                "ticker": "TEST",
                "asOf": "2026-01-01",
                "raw": {"earnings_yield": 0.1, "sales_yield": 2, "liabilities_to_assets": 0.2, "return_90d": 0.1, "return_30d": 0.05, "annualized_volatility": 0.2, "max_drawdown_1y": -0.1, "revenue_growth": 0.1, "net_margin": 0.2, "net_margin_trend": 0.01},
                "percentile": {"earnings_yield": 0.9, "sales_yield": 0.9, "liabilities_to_assets": 0.1, "return_90d": 0.5, "return_30d": 0.5, "annualized_volatility": 0.1, "max_drawdown_1y": 0.9, "revenue_growth": 0.7, "net_margin": 0.7, "net_margin_trend": 0.7},
                "balanceSheetScoring": {"balanceSheetQualityScore": 10, "balanceSheetRiskPenalty": 95, "confidenceAdjustment": -10, "triggeredRiskGates": [{"name": "Severe Leverage Gate", "severity": "severe", "triggered": True}], "targetComparisons": [], "warnings": []},
            }
            scored = score_record(row)
            self.assertEqual(scored["signal"], "value-trap-risk")
            self.assertTrue(scored["balanceSheetOfficialChange"]["changed"])
        finally:
            if previous is None:
                os.environ.pop("BALANCE_SHEET_SCORING_MODE", None)
            else:
                os.environ["BALANCE_SHEET_SCORING_MODE"] = previous


if __name__ == "__main__":
    unittest.main()
