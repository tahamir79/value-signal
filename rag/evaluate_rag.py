from __future__ import annotations

import argparse
import json
import re

from rag.rag_pipeline import run_rag

QUERIES = ["Why was this stock flagged as potentially undervalued?", "What risks could make this company a value trap?",
           "Does the company disclose margin pressure?", "Does the company mention liquidity or debt risk?",
           "Are there signs of weak demand?", "What should I research next?"]
ADVICE = re.compile(r"\b(buy|sell|hold|guaranteed upside|this stock will go (?:up|down))\b", re.I)


def evaluate(ticker: str, *, synthesize: bool = False) -> dict:
    cases = []
    for query in QUERIES:
        result = run_rag(query, ticker=ticker, synthesize=synthesize)
        ids = set(result["citations"]); answer = result["answer"] or ""
        cases.append({"query": query, "retrieved": len(result["retrieved_chunks"]),
                      "citationValidity": all(cid in ids for cid in re.findall(r"\b[A-Z0-9][A-Za-z0-9_.:-]{5,}\b", answer) if cid in ids),
                      "answerCitesEvidence": not answer or any(cid in answer for cid in ids),
                      "avoidsAdvice": not bool(ADVICE.search(answer)),
                      "insufficientWhenEmpty": bool(result["retrieved_chunks"]) or "insufficient" in (result["limitations"] or answer).lower()})
    return {"ticker": ticker, "cases": cases, "passed": all(all(v for k,v in row.items() if k not in {"query","retrieved"}) for row in cases)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate local filing-grounded RAG")
    parser.add_argument("--ticker", default="COST"); parser.add_argument("--synthesize", action="store_true")
    args = parser.parse_args(); report = evaluate(args.ticker, synthesize=args.synthesize)
    print(json.dumps(report, indent=2)); return 0 if report["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
