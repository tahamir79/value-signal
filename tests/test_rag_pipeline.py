import unittest

from rag.hybrid_retriever import retrieve
from rag.intent import RISK_OUTLOOK_INTENT, detect_intent, deterministic_risk_posture, expanded_queries
from rag.prompt_builder import build_prompt
from rag.rag_pipeline import _guard_signal_relationship, run_rag
from rag.stock_context import extract_evidence_assessment, normalize_evidence_relevance, normalize_signal_relationship, stock_context_summary
from rag.synthesis_profile import DEEP_MODE, QUICK_MODE, profile_for
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
        self.assertIn("Evidence Relevance:",prompt)
        self.assertIn("Signal Relationship:",prompt)
        self.assertEqual(extract_evidence_assessment("Evidence Assessment: Review recommended\nBecause..."),"Review recommended")
        self.assertIn("Structured pipeline context",stock_context_summary(None))
    def test_risk_outlook_intent_and_prompt(self):
        query="should i expect this to hold value or go up or down? assess based on risk data"
        self.assertEqual(detect_intent(query),RISK_OUTLOOK_INTENT)
        self.assertEqual(len(expanded_queries(query,RISK_OUTLOOK_INTENT)),3)
        prompt=build_prompt(query,CHUNKS,ticker="COST",intent=RISK_OUTLOOK_INTENT,stock_context={"officialSignalLabel":"Neutral","officialSignal":"neutral","scores":{"marketRisk":80,"value":20}})
        self.assertIn("I cannot predict whether the stock will go up or down",prompt)
        self.assertIn("Risk-Based Assessment:",prompt)
        self.assertEqual(deterministic_risk_posture({"scores":{"marketRisk":80}}),"elevated risk")
    def test_risk_outlook_run_uses_expanded_retrieval(self):
        result=run_rag("is the signal strong enough?", "COST", retrieval_mode="bm25", index=self.index, synthesize=False)
        self.assertEqual(result["intent"],RISK_OUTLOOK_INTENT)
        self.assertGreaterEqual(len(result["retrieved_chunks"]),1)
        self.assertIn(result["deterministic_risk_posture"],{"supportive","mixed","elevated risk","insufficient"})
    def test_risk_outlook_safety_preface_is_enforced(self):
        cid=CHUNKS[0]["chunkId"]
        result=run_rag("should it go up or down?", "COST", retrieval_mode="bm25", index=self.index,
                       generator=lambda _prompt:f"Evidence Assessment: Mixed evidence\nCitations: {cid}")
        self.assertIn("I cannot predict whether the stock will go up or down",result["answer"])
    def test_deep_research_profile_and_fields(self):
        self.assertEqual(profile_for(None,"Further review of cybersecurity impact").name,DEEP_MODE)
        self.assertEqual(profile_for(QUICK_MODE,"x").max_output_tokens,300)
        self.assertEqual(detect_intent("Further review of cybersecurity risk management practices"),"cybersecurity_risk_review")
        prompt=build_prompt("Further review of cybersecurity risk management practices",CHUNKS,ticker="COST",intent="cybersecurity_risk_review",synthesis_depth=DEEP_MODE,session_summary="Prior intent: risk; previous chunk IDs: abc.")
        self.assertIn("Research Answer:",prompt)
        self.assertIn("Research Session Summary",prompt)
        self.assertEqual(normalize_evidence_relevance("Directly relevant to cybersecurity governance"),"Directly relevant to question")
        self.assertEqual(normalize_signal_relationship("Indirect relationship to Momentum risk"),"Indirect relationship")
    def test_deep_research_run_returns_relevance_relationship(self):
        cid=CHUNKS[0]["chunkId"]
        result=run_rag("Further review of liquidity debt risk impact", "COST", retrieval_mode="bm25", index=self.index,
                       generator=lambda _prompt, max_output_tokens=None:f"Research Answer: test {cid}\nEvidence Relevance: Directly relevant to question\nSignal Relationship: Indirect relationship\nCitations: {cid}")
        self.assertEqual(result["synthesis_depth"],DEEP_MODE)
        self.assertEqual(result["evidence_relevance"],"Directly relevant to question")
        self.assertEqual(result["signal_relationship"],"Indirect relationship")
    def test_thematic_review_does_not_overconnect_signal(self):
        guarded=_guard_signal_relationship("cybersecurity_risk_review","Supports signal","Momentum risk","Cybersecurity governance is mature.")
        self.assertEqual(guarded,"Indirect relationship")

if __name__ == "__main__": unittest.main()
