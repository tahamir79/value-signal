import unittest
from scripts.scoring import classify, component_score, confidence_for, reason_codes, score_record, sensitivity_scenarios

def feature_row(value=0.5, missing=()):
    names=("earnings_yield","sales_yield","net_margin","revenue_growth","net_margin_trend","return_90d","return_30d","max_drawdown_1y","annualized_volatility","liabilities_to_assets")
    raw={name:(None if name in missing else value) for name in names}
    percentile=dict(raw)
    return {"ticker":"TEST","asOf":"2026-01-01","raw":raw,"percentile":percentile}

class ScoringTests(unittest.TestCase):
    def test_component_is_bounded_and_contributions_sum_to_score(self):
        result=component_score({"a":1.5,"b":-0.5},{"a":0.5,"b":0.5},set())
        self.assertEqual(result["score"],50.0)
        self.assertAlmostEqual(sum(item["points"] for item in result["contributions"]),result["score"])

    def test_missing_feature_renormalizes_weight_and_reduces_confidence(self):
        result=component_score({"a":0.8,"b":None},{"a":0.5,"b":0.5},set())
        self.assertEqual(result["score"],80.0); self.assertEqual(result["coverage"],0.5)
        confidence,available=confidence_for(feature_row(missing=("sales_yield","net_margin","revenue_growth"))["raw"])
        self.assertEqual((confidence,available),("Medium",7))

    def test_exact_label_boundaries_and_priority(self):
        self.assertEqual(classify({"value":70,"quality":50,"momentumRisk":20,"marketRisk":69.999,"balanceSheetRisk":69.999},"High"),"potentially-undervalued")
        self.assertEqual(classify({"value":65,"quality":90,"momentumRisk":80,"marketRisk":10,"balanceSheetRisk":70},"High"),"value-trap-risk")
        self.assertEqual(classify({"value":90,"quality":90,"momentumRisk":70,"marketRisk":10,"balanceSheetRisk":10},"High"),"momentum-risk")
        self.assertEqual(classify({"value":20,"quality":70,"momentumRisk":20,"marketRisk":10,"balanceSheetRisk":69.999},"High"),"quality-watchlist")
        self.assertEqual(classify({"value":100,"quality":100,"momentumRisk":0,"marketRisk":0,"balanceSheetRisk":0},"Insufficient"),"insufficient-evidence")

    def test_reason_codes_match_score_direction(self):
        scores={"value":75,"quality":25,"momentumRisk":75,"marketRisk":75,"balanceSheetRisk":75}
        codes=reason_codes(scores,"High")
        self.assertIn("VALUE_STRONG",codes); self.assertIn("QUALITY_WEAK",codes); self.assertIn("MOMENTUM_RISK_HIGH",codes); self.assertIn("BALANCE_SHEET_RISK_HIGH",codes)

    def test_record_is_deterministic_and_sensitivity_is_enumerated(self):
        row=feature_row()
        self.assertEqual(score_record(row),score_record(row))
        self.assertEqual(len(sensitivity_scenarios([row])),20)

if __name__=="__main__": unittest.main()
