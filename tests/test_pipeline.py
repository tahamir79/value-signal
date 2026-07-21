import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from scripts.models import PriceBar, Security
from scripts.providers.price_provider import FixturePriceProvider
from scripts.providers.sec_companyfacts import FixtureCompanyFactsProvider
from scripts.run_etl import run
from scripts.run_etl import _securities_from_universe_file
from scripts.run_etl import remove_stale_stock_artifacts

def facts(value=100): return {"facts":{"us-gaap":{"Assets":{"units":{"USD":[{"val":value,"end":"2025-12-31","filed":"2026-02-01","fy":2025,"fp":"FY","form":"10-K","accn":"x"}]}}}}}

class PipelineTests(unittest.TestCase):
    def test_one_ticker_failure_does_not_stop_run(self):
        bar=lambda ticker,close:PriceBar(ticker,"2026-01-02",close,close,close,close,1000,"fixture")
        with tempfile.TemporaryDirectory() as directory:
            audit=run(FixturePriceProvider({"AAPL":[bar("AAPL",10),bar("AAPL",11)]}),FixtureCompanyFactsProvider({"0000320193":facts()}),Path(directory),limit=2)
            self.assertEqual(audit["successfulTickers"],1); self.assertEqual(audit["failedTickers"],1); self.assertEqual(audit["status"],"partial_success")
            dashboard=json.loads((Path(directory)/"dashboard.json").read_text())
            self.assertEqual(dashboard["schemaVersion"],"1.0.0"); self.assertEqual(dashboard["records"][0]["security"]["ticker"],"AAPL")
            features=json.loads((Path(directory)/"features.json").read_text())
            self.assertEqual(features["universeSize"],1)
            self.assertEqual(features["records"][0]["percentile"]["return_30d"],None)
            signals=json.loads((Path(directory)/"signals.json").read_text())
            self.assertEqual(signals["universeSize"],1)
            self.assertEqual(signals["records"][0]["signal"],"insufficient-evidence")
            backtest=json.loads((Path(directory)/"backtest_results.json").read_text())
            self.assertEqual(backtest["status"],"insufficient_data")

    def test_growth_spurt_artifacts_are_published_without_changing_scoring(self):
        def series(ticker: str, daily_growth: float) -> list[PriceBar]:
            start = date(2025, 1, 1)
            rows = []
            for index in range(130):
                close = 100 * (daily_growth ** index)
                rows.append(PriceBar(ticker, (start + timedelta(days=index)).isoformat(), close, close, close, close, 1000, "fixture", close))
            return rows

        security = Security("AAPL", "0000320193", "Apple Inc.", "NASDAQ", "Technology")
        with tempfile.TemporaryDirectory() as directory:
            audit = run(
                FixturePriceProvider({"AAPL": series("AAPL", 1.003), "SPY": series("SPY", 1.001)}),
                FixtureCompanyFactsProvider({"0000320193": facts()}),
                Path(directory),
                securities=[security],
                include_backtest=False,
            )
            self.assertEqual(audit["successfulTickers"], 1)
            self.assertEqual(audit["growthSpurtCoverage"]["stocksGrowthSpurtDetected"], 1)
            dashboard = json.loads((Path(directory) / "dashboard.json").read_text())
            self.assertEqual(dashboard["records"][0]["growthSpurt"]["status"], "detected")
            detail = json.loads((Path(directory) / "stocks" / "AAPL.json").read_text())
            self.assertEqual(detail["record"]["growthSpurt"]["status"], "detected")
            signals = json.loads((Path(directory) / "signals.json").read_text())
            self.assertEqual(signals["records"][0]["signal"], "insufficient-evidence")

    def test_scaled_universe_file_feeds_existing_etl(self):
        payload={"records":[
            {"ticker":"AAPL","cik":"320193","companyName":"Apple Inc.","exchange":"NASDAQ","sector":"Technology","isSupported":True},
            {"ticker":"ETF","cik":"1","companyName":"Example ETF","exchange":"NYSE","sector":None,"isSupported":False},
            {"ticker":"MSFT","cik":"789019","companyName":"Microsoft Corp.","exchange":"NASDAQ","sector":"Technology","isSupported":True},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"universe.json"
            path.write_text(json.dumps(payload),encoding="utf-8")
            securities=_securities_from_universe_file(path)
            self.assertEqual([security.ticker for security in securities],["AAPL","MSFT"])
            self.assertEqual(securities[0].cik,"0000320193")

    def test_stale_stock_artifact_cleanup_preserves_summary_and_active_tickers(self):
        with tempfile.TemporaryDirectory() as directory:
            stock_dir=Path(directory)/"stocks"
            stock_dir.mkdir()
            (stock_dir/"summary.json").write_text("{}",encoding="utf-8")
            (stock_dir/"AAPL.json").write_text("{}",encoding="utf-8")
            (stock_dir/"OLD.json").write_text("{}",encoding="utf-8")
            removed=remove_stale_stock_artifacts(Path(directory),{"AAPL"})
            self.assertEqual(removed,["OLD"])
            self.assertTrue((stock_dir/"summary.json").exists())
            self.assertTrue((stock_dir/"AAPL.json").exists())
            self.assertFalse((stock_dir/"OLD.json").exists())

if __name__=="__main__": unittest.main()
