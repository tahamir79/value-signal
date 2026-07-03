import unittest

from scripts.build_search_index import bm25_search,build_index,tokenize
from scripts.chunk_filings import chunk_filing
from scripts.providers.sec_filings import FilingDocument
from scripts.text_cleaning import clean_filing_html


def filing():
    return FilingDocument("TEST","0000000001","0000000001-26-000001","2026-02-01","2025-12-31","10-K","test.htm","https://www.sec.gov/Archives/edgar/data/1/000000000126000001/test.htm","")


class RetrievalTests(unittest.TestCase):
    def test_cleaner_removes_markup_scripts_and_repeated_headers(self):
        source="<html><script>secret()</script><body>"+("<p>ACME 2025 FORM 10-K</p>"*4)+"<h2>Item 1A. Risk Factors</h2><p>Supply chain disruption could interrupt production.</p></body></html>"
        cleaned=clean_filing_html(source)
        self.assertNotIn("secret",cleaned); self.assertNotIn("<p>",cleaned); self.assertNotIn("ACME 2025",cleaned)
        self.assertIn("Supply chain disruption",cleaned)

    def test_metadata_survives_chunking_and_empty_chunks_are_removed(self):
        text="Item 1A. Risk Factors\n"+"Cybersecurity incidents may disrupt operations and expose customer information. "*35
        chunks=chunk_filing(filing(),text,target_words=80,overlap_words=15,minimum_words=20)
        self.assertGreater(len(chunks),1)
        for chunk in chunks:
            self.assertEqual(chunk["accession"],filing().accession); self.assertEqual(chunk["form"],"10-K")
            self.assertEqual(chunk["item"],"Item 1A. Risk Factors"); self.assertTrue(chunk["url"].startswith("https://www.sec.gov/Archives/")); self.assertTrue(chunk["text"].strip())

    def test_bm25_ranks_relevant_passage_and_traces_terms(self):
        base={"ticker":"TEST","accession":"a","filingDate":"2026-01-01","reportDate":"2025-12-31","form":"10-K","url":"https://www.sec.gov/a","wordStart":0,"wordEnd":30}
        chunks=[{**base,"id":"risk","item":"Item 1A","text":"Supply chain concentration and sole source suppliers may disrupt production and increase costs."},{**base,"id":"other","item":"Item 7","text":"Revenue increased due to product demand and foreign currency movements."}]
        index=build_index(chunks)
        results=bm25_search(index,"supplier supply chain risk",ticker="TEST")
        self.assertEqual(results[0]["id"],"risk"); self.assertIn("supply",results[0]["matchedTerms"]); self.assertGreater(results[0]["score"],0)
        self.assertIn("supplier",tokenize("The supplier and the supply chain"))

    def test_ticker_filter_and_complete_citation(self):
        base={"accession":"a","filingDate":"2026-01-01","reportDate":"2025-12-31","form":"10-Q","item":"Item 1A","text":"Liquidity risk and debt maturity risk.","url":"https://www.sec.gov/Archives/example","wordStart":0,"wordEnd":10}
        index=build_index([{**base,"id":"a","ticker":"AAA"},{**base,"id":"b","ticker":"BBB"}])
        results=bm25_search(index,"liquidity risk",ticker="BBB")
        self.assertEqual([row["ticker"] for row in results],["BBB"]); self.assertEqual(results[0]["url"],base["url"])


if __name__=="__main__": unittest.main()
