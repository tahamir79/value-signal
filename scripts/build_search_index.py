from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_universe import build_universe
from scripts.chunk_filings import chunk_filing
from scripts.export_json import write_json
from scripts.providers.sec_filings import SecFilingProvider
from scripts.retrieval import diversify_results
from scripts.text_cleaning import clean_filing_html

SEARCH_SCHEMA_VERSION = "3.0.0"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
STOPWORDS = {"a","an","and","are","as","at","be","by","for","from","has","in","is","it","of","on","or","that","the","this","to","was","were","will","with"}


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOPWORDS and len(token) > 1]


def build_index(chunks: list[dict[str, Any]], errors: list[dict[str, str]] | None = None) -> dict[str, Any]:
    documents = []
    postings: dict[str, list[list[int]]] = defaultdict(list)
    lengths = []
    for doc_id, chunk in enumerate(chunks):
        tokens = tokenize(chunk["text"])
        if not tokens:
            continue
        documents.append(chunk)
        lengths.append(len(tokens))
        for term, frequency in Counter(tokens).items():
            postings[term].append([len(documents) - 1, frequency])
    return {
        "schemaVersion": SEARCH_SCHEMA_VERSION, "generatedAt": datetime.now(timezone.utc).isoformat(),
        "corpusHash": hashlib.sha256("\n".join(str(row.get("chunkId") or row.get("id")) for row in documents).encode()).hexdigest(),
        "status": "success" if not errors else "partial_success", "documentCount": len(documents),
        "averageDocumentLength": round(sum(lengths) / len(lengths), 4) if lengths else 0,
        "documentLengths": lengths, "documents": documents, "postings": dict(sorted(postings.items())), "errors": errors or [],
    }


def bm25_search(index: dict[str, Any], query: str, ticker: str | None = None, limit: int = 5,
                k1: float = 1.5, b: float = 0.75, form: str | None = None,
                apply_diversification: bool = True) -> list[dict[str, Any]]:
    scores: dict[int, float] = defaultdict(float)
    terms = tokenize(query)
    total = index.get("documentCount", 0)
    average = index.get("averageDocumentLength", 0) or 1
    for term in terms:
        posting = index.get("postings", {}).get(term, [])
        document_frequency = len(posting)
        if not document_frequency:
            continue
        inverse = math.log(1 + (total - document_frequency + 0.5) / (document_frequency + 0.5))
        for doc_id, frequency in posting:
            if ticker and index["documents"][doc_id]["ticker"] != ticker:
                continue
            if form and (index["documents"][doc_id].get("formType") or index["documents"][doc_id].get("form")) != form:
                continue
            length = index["documentLengths"][doc_id]
            scores[doc_id] += inverse * (frequency * (k1 + 1)) / (frequency + k1 * (1 - b + b * length / average))
    ranked = [{**index["documents"][doc_id], "score": round(score, 6), "matchedTerms": [term for term in terms if any(row[0] == doc_id for row in index["postings"].get(term, []))]} for doc_id, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]
    return diversify_results(ranked, limit) if apply_diversification else ranked[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the ValueSignal SEC filing search index")
    parser.add_argument("--output", type=Path, default=Path("public/data/search_index.json"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--per-form", type=int, default=1)
    args = parser.parse_args()
    user_agent = os.getenv("VS_USER_AGENT", "")
    if not user_agent or "@" not in user_agent:
        print("VS_USER_AGENT must identify the application and include a contact email.", file=sys.stderr)
        return 2
    provider = SecFilingProvider(user_agent)
    chunks, errors = [], []
    for security in build_universe(args.limit):
        try:
            for filing in provider.fetch_recent(security.ticker, security.cik, args.per_form):
                filing_chunks = chunk_filing(filing, clean_filing_html(filing.html))
                for chunk in filing_chunks:
                    chunk["companyName"] = security.company_name
                chunks.extend(filing_chunks)
        except Exception as exc:
            errors.append({"ticker": security.ticker, "message": f"{type(exc).__name__}: {exc}"})
    index = build_index(chunks, errors)
    write_json(args.output, index)
    print(f"Search index {index['status']}: {index['documentCount']} chunks, {len(index['postings'])} terms")
    return 0 if index["documentCount"] else 1


if __name__ == "__main__": raise SystemExit(main())
