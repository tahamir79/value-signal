import json
import tempfile
import unittest
from pathlib import Path
from scripts.models import PriceBar
from scripts.providers.price_provider import FixturePriceProvider
from scripts.providers.sec_companyfacts import FixtureCompanyFactsProvider
from scripts.run_etl import run
from scripts.run_etl import _securities_from_universe_file

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

if __name__=="__main__": unittest.main()
