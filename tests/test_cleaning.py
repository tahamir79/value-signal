import unittest
from scripts.cleaning import latest_facts, normalize_company_facts

class CleaningTests(unittest.TestCase):
    def test_normalizes_supported_fact_and_ignores_bad_forms(self):
        payload={"facts":{"us-gaap":{"Assets":{"units":{"USD":[{"val":100,"end":"2025-12-31","filed":"2026-02-01","fy":2025,"fp":"FY","form":"10-K","accn":"a"},{"val":999,"end":"2026-01-01","filed":"2026-01-02","form":"8-K","accn":"b"}]}}}}}
        facts=normalize_company_facts(payload)
        self.assertEqual(len(facts),1); self.assertEqual(facts[0].value,100.0)

    def test_latest_fact_uses_period_then_filing_date(self):
        payload={"facts":{"us-gaap":{"NetIncomeLoss":{"units":{"USD":[{"val":8,"end":"2024-12-31","filed":"2025-02-01","form":"10-K","accn":"a"},{"val":10,"end":"2025-12-31","filed":"2026-02-01","form":"10-K","accn":"b"}]}}}}}
        self.assertEqual(latest_facts(normalize_company_facts(payload))["Net income"].value,10.0)

if __name__=="__main__": unittest.main()
