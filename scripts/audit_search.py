from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_search_index import bm25_search


def audit(index_path: Path = Path("public/data/search_index.json"), queries_path: Path = Path("tests/fixtures/retrieval_queries.json")) -> list[str]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    documents = index.get("documents", [])
    if index.get("documentCount") != len(documents) or len(index.get("documentLengths", [])) != len(documents):
        failures.append("index document counts do not reconcile")
    required = {"id", "ticker", "accession", "filingDate", "form", "item", "url", "text"}
    for document in documents:
        missing = required - document.keys()
        if missing:
            failures.append(f"{document.get('id', '?')}: missing metadata {sorted(missing)}")
        if not document.get("text", "").strip():
            failures.append(f"{document.get('id', '?')}: empty chunk")
        if not document.get("url", "").startswith("https://www.sec.gov/Archives/"):
            failures.append(f"{document.get('id', '?')}: citation does not resolve to SEC Archives")
    print(f"FILING FETCH/CHUNKS: {'PASS' if documents else 'AWAITING REFRESH'} ({len(documents)} chunks)")
    print(f"METADATA/CITATIONS: {'PASS' if not failures else 'FAIL'}")
    frequencies = Counter({term: sum(row[1] for row in posting) for term, posting in index.get("postings", {}).items()})
    print("TOP TOKEN FREQUENCIES: " + ", ".join(f"{term}={count}" for term, count in frequencies.most_common(10)))
    if documents:
        queries = json.loads(queries_path.read_text(encoding="utf-8"))
        for case in queries:
            results = bm25_search(index, case["query"], limit=3)
            if not results:
                failures.append(f"query returned no results: {case['query']}")
                continue
            first = results[0]
            print(f"BM25 TRACE: query={case['query']!r} top={first['ticker']} {first['form']} {first['item']} score={first['score']} terms={first['matchedTerms']}")
    else:
        print("BM25 TRACE: awaiting first live SEC filing index")
    return failures


if __name__ == "__main__":
    problems = audit()
    if problems:
        print("\n".join(problems))
    raise SystemExit(1 if problems else 0)
