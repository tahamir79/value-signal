import json
import tempfile
import unittest
from pathlib import Path
from scripts.models import PriceBar
from scripts.providers.price_provider import FixturePriceProvider
from scripts.providers.sec_companyfacts import FixtureCompanyFactsProvider
from scripts.run_etl import run

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

if __name__=="__main__": unittest.main()
