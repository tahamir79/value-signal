import unittest
from datetime import date,timedelta

from scripts.backtest import build_point_in_time_snapshots,evaluate_snapshots
from scripts.models import FinancialFact,PriceBar


def bars(ticker,start="2025-01-01",count=150,growth=0.001):
    origin=date.fromisoformat(start)
    return [PriceBar(ticker,(origin+timedelta(days=index)).isoformat(),100*(1+growth)**index,101,99,100*(1+growth)**index,1000,"fixture",100*(1+growth)**index) for index in range(count)]


def snapshot(ticker="AAA",signal_date="2025-01-10"):
    return {"ticker":ticker,"signal":"neutral","signalDate":signal_date,"availableAt":signal_date,"sourcePriceThrough":signal_date,"sourceMaxFiledAt":"2025-01-09"}


class BacktestTests(unittest.TestCase):
    def test_signal_precedes_outcome_and_forward_return_is_exact(self):
        security=bars("AAA"); benchmark=bars("SPY",growth=0.0005)
        report=evaluate_snapshots([snapshot()],{"AAA":security},benchmark,["AAA"])
        trace=report["traceObservation"]
        self.assertLess(trace["signalDate"],trace["entryDate"]); self.assertLess(trace["entryDate"],trace["outcomeDate"])
        self.assertAlmostEqual(trace["forwardReturn"],(1.001**30)-1,places=6)
        self.assertAlmostEqual(trace["benchmarkReturn"],(1.0005**30)-1,places=6)

    def test_future_source_is_rejected_as_leakage(self):
        leaked=snapshot(); leaked["sourceMaxFiledAt"]="2025-01-11"
        report=evaluate_snapshots([leaked],{"AAA":bars("AAA")},bars("SPY"),["AAA"])
        self.assertEqual(report["status"],"insufficient_data"); self.assertEqual(report["biasAudit"]["rejectedForLeakage"],1)

    def test_benchmark_dates_must_align(self):
        report=evaluate_snapshots([snapshot()],{"AAA":bars("AAA")},bars("SPY",start="2026-01-01"),["AAA"])
        self.assertEqual(report["evaluatedObservationCount"],0); self.assertGreater(report["biasAudit"]["rejectedForDateAlignment"],0)

    def test_samples_and_overlapping_windows_are_reported(self):
        snapshots=[snapshot(signal_date="2025-01-10"),snapshot(signal_date="2025-01-20")]
        report=evaluate_snapshots(snapshots,{"AAA":bars("AAA")},bars("SPY"),["AAA","DELISTED"])
        cohort=next(row for row in report["cohorts"] if row["horizonSessions"]==30 and row["marketRegime"]=="all")
        self.assertEqual(cohort["sampleCount"],2); self.assertIsNotNone(cohort["excessReturnConfidenceInterval95"])
        self.assertGreater(report["biasAudit"]["overlappingWindows"],0); self.assertEqual(report["biasAudit"]["missingExpectedSymbols"],["DELISTED"])

    def test_snapshot_uses_only_facts_filed_by_signal_date(self):
        old=FinancialFact("Assets","Assets",100,"USD","2024-12-31","2025-01-05",2024,"FY","10-K","old")
        future=FinancialFact("Assets","Assets",999,"USD","2025-12-31","2026-02-01",2025,"FY","10-K","future")
        snapshots=build_point_in_time_snapshots({"AAA":bars("AAA",count=45)},{"AAA":[old,future]},["2025-01-20"])
        self.assertEqual(len(snapshots),1); self.assertEqual(snapshots[0]["sourceMaxFiledAt"],"2025-01-05")
        self.assertLessEqual(snapshots[0]["sourcePriceThrough"],snapshots[0]["signalDate"])


if __name__=="__main__": unittest.main()
