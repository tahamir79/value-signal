import unittest

from rag.hybrid_retriever import retrieve
from rag.prompt_builder import build_prompt
from rag.rag_pipeline import run_rag
from rag.stock_context import extract_evidence_assessment, stock_context_summary
from rag.synthesize import validate_answer
from scripts.build_search_index import build_index

CHUNKS = [{"id":"COST_2024_10K_ITEM1A_abcde","chunkId":"COST_2024_10K_ITEM1A_abcde","ticker":"COST","companyName":"Costco",
           "form":"10-K","filingDate":"2024-10-01","sectionKey":"part-i:item-1a","sourceUrl":"https://sec.example","text":"Debt and liquidity risks may increase costs."}]

class RagPipelineTests(unittest.TestCase):
    def setUp(self): self.index = build_index(CHUNKS)
    def test_bm25_and_evidence_only(self):
        result=run_rag("liquidity debt risk", "cost", synthesize=False, index=self.index)
        self.assertEqual(result["ticker"],"COST"); self.assertEqual(len(result["retrieved_chunks"]),1)
    def test_hybrid_falls_back(self):
        rows,warnings,mode=retrieve("liquidity",ticker="COST",index=self.index,embedding_search=lambda *a,**k:[])
        self.assertEqual(mode,"bm25"); self.assertTrue(warnings); self.assertTrue(rows)
    def test_prompt_is_bounded(self):
        prompt=build_prompt("risks?",CHUNKS,ticker="COST",max_context_chars=1600)
        self.assertLessEqual(len(prompt),1600); self.assertIn(CHUNKS[0]["chunkId"],prompt)
    def test_safety_filter(self):
        answer,warnings=validate_answer("Buy this stock",{CHUNKS[0]["chunkId"]})
        self.assertIn("withheld",answer); self.assertTrue(warnings)
        answer,warnings=validate_answer("Grounded claim [abcdef123456].",{"abcdef123456"})
        self.assertFalse(warnings)
    def test_mocked_synthesis(self):
        cid=CHUNKS[0]["chunkId"]
        result=run_rag("liquidity", "COST", retrieval_mode="bm25", index=self.index,
                       generator=lambda prompt:f"Evidence Assessment: Mixed evidence\nRAG Interpretation: Evidence may indicate risk [{cid}].")
        self.assertIn(cid,result["answer"])
        self.assertEqual(result["evidence_assessment"],"Mixed evidence")
    def test_stock_context_prompt_and_assessment(self):
        prompt=build_prompt("risks?",CHUNKS,ticker="COST",stock_context={"officialSignalLabel":"Value trap risk","officialSignal":"value-trap-risk","confidence":"High","scores":{"value":90},"rawFeatures":{"earnings_yield":.1}})
        self.assertIn("Official deterministic signal: Value trap risk",prompt)
        self.assertIn("Evidence Assessment:",prompt)
        self.assertEqual(extract_evidence_assessment("Evidence Assessment: Review recommended\nBecause..."),"Review recommended")
        self.assertIn("Structured pipeline context",stock_context_summary(None))

if __name__ == "__main__": unittest.main()
