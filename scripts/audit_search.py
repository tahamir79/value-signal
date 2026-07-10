from __future__ import annotations

import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

if __package__ in {None, ""}: sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_search_index import bm25_search
from scripts.chunk_filings import TEN_K_PARTS, TEN_Q_ITEMS
from scripts.retrieval import diversify_results

CORE = {"id", "ticker", "accession", "filingDate", "form", "item", "url", "text"}
SCHEMA3 = {"chunkId", "cik", "primaryDocument", "part", "itemNumber", "sectionKey", "sectionTitle", "chunkSequence", "boundaryType", "paragraphRange", "sentenceRange", "sectionWordStart", "sectionWordEnd", "documentWordStart", "documentWordEnd", "documentCharStart", "documentCharEnd", "previousChunkId", "nextChunkId"}


def _jaccard(a: str, b: str) -> float:
    left, right = set(a.lower().split()), set(b.lower().split())
    return len(left & right) / len(left | right) if left or right else 1


def audit(index_path: Path = Path("public/data/search_index.json"), queries_path: Path = Path("tests/fixtures/retrieval_queries.json")) -> list[str]:
    index=json.loads(index_path.read_text(encoding="utf-8")); documents=index.get("documents",[]); failures=[]
    if index.get("documentCount")!=len(documents) or len(index.get("documentLengths",[]))!=len(documents): failures.append("index document counts do not reconcile")
    if len({row.get("id") for row in documents})!=len(documents): failures.append("chunk IDs are not unique")
    schema3=index.get("schemaVersion")=="3.0.0"; missing=Counter(); tickers=Counter(); forms=Counter(); sections=Counter(); filings=defaultdict(list); fallback=front_matter=0
    for row in documents:
        absent=CORE-row.keys()
        if schema3: absent|=SCHEMA3-row.keys()
        for key in absent: missing[key]+=1
        if absent: failures.append(f"{row.get('id','?')}: missing metadata {sorted(absent)}")
        if not row.get("text","").strip(): failures.append(f"{row.get('id','?')}: empty chunk")
        url=row.get("sourceUrl") or row.get("url","")
        if not url.startswith("https://www.sec.gov/Archives/"): failures.append(f"{row.get('id','?')}: citation does not resolve to SEC Archives")
        for start,end,name in ((row.get("documentWordStart"),row.get("documentWordEnd"),"word"),(row.get("documentCharStart"),row.get("documentCharEnd"),"character")):
            if start is not None and (not isinstance(start,int) or not isinstance(end,int) or start<0 or end<start): failures.append(f"{row.get('id','?')}: invalid {name} offsets")
        tickers[row.get("ticker","?")]+=1; forms[row.get("formType") or row.get("form","?")]+=1; sections[row.get("sectionKey") or row.get("item","unclassified")]+=1; filings[(row.get("ticker"),row.get("accession"))].append(row)
        fallback+=row.get("boundaryType")=="fixed_window_fallback"; front_matter+=not (row.get("sectionKey") or row.get("item"))
        text=row.get("text","").lower()
        if row.get("sectionKey")=="part-iv:item-16" and "signatures" in text: failures.append(f"{row.get('id','?')}: Item 16 contains signatures")
        if str(row.get("sectionKey","")).startswith("preamble:") and re.search(r"(?im)^(?:part|item|signatures?)\b",row.get("text","")): failures.append(f"{row.get('id','?')}: preamble crosses a structural boundary")
        number=str(row.get("itemNumber") or "").lower(); part=str(row.get("part") or "").lower(); form=row.get("formType") or row.get("form")
        if form=="10-K" and number and TEN_K_PARTS.get(number)!=part: failures.append(f"{row.get('id','?')}: invalid 10-K Part/Item mapping")
        if form=="10-Q" and number and (part not in TEN_Q_ITEMS or number not in TEN_Q_ITEMS[part]): failures.append(f"{row.get('id','?')}: invalid 10-Q Part/Item mapping")
    near_duplicates=sum(_jaccard(documents[i].get("text",""),documents[j].get("text",""))>.70 for i in range(len(documents)) for j in range(i+1,len(documents)) if documents[i].get("accession")==documents[j].get("accession"))
    for (ticker,accession),rows in filings.items():
        counts=Counter(row.get("sectionKey") for row in rows)
        if len(rows)>=10 and counts and counts.most_common(1)[0][1]/len(rows)>.75:
            failures.append(f"{ticker}/{accession}: one section owns more than 75% of filing chunks")
    lengths=index.get("documentLengths",[]); distribution={"min":min(lengths,default=0),"median":sorted(lengths)[len(lengths)//2] if lengths else 0,"max":max(lengths,default=0)}
    print(f"FILING FETCH/CHUNKS: {'PASS' if documents else 'AWAITING REFRESH'} ({len(documents)} chunks)")
    print(f"SCHEMA/METADATA/CITATIONS: {'PASS' if not failures else 'FAIL'} schema={index.get('schemaVersion')} missing={dict(missing)}")
    print(f"CHUNK DISTRIBUTION: {distribution} fallback_windows={fallback} front_matter={front_matter} near_duplicates={near_duplicates}")
    print(f"BY TICKER: {dict(tickers)}\nBY FORM: {dict(forms)}\nBY SECTION: {dict(sections)}")
    print("PER FILING: "+", ".join(f"{ticker}/{accession}={len(rows)}" for (ticker,accession),rows in sorted(filings.items())))
    if documents:
        cases=json.loads(queries_path.read_text(encoding="utf-8")); precision=reciprocal=raw_precision=raw_reciprocal=0.0
        for case in cases:
            ranked=bm25_search(index,case["query"],limit=20,apply_diversification=False); results=diversify_results(ranked,3)
            expected=set(case.get("expectedSectionKeys",[]))
            raw_hits=[i for i,row in enumerate(ranked[:3]) if not expected or row.get("sectionKey") in expected]
            hits=[i for i,row in enumerate(results) if not expected or row.get("sectionKey") in expected]
            raw_precision+=len(raw_hits)/3; raw_reciprocal+=(1/(raw_hits[0]+1) if raw_hits else 0)
            precision+=(len(hits)/3); reciprocal+=(1/(hits[0]+1) if hits else 0)
            if not results: failures.append(f"query returned no results: {case['query']}")
            else: print(f"BM25 TRACE: query={case['query']!r} top={results[0]['ticker']} {results[0].get('sectionKey') or results[0].get('item')} score={results[0]['score']}")
        count=len(cases) or 1; print(f"RAW BM25 EVAL: precision@3={raw_precision/count:.4f} MRR={raw_reciprocal/count:.4f}")
        print(f"DIVERSIFIED EVAL: precision@3={precision/count:.4f} MRR={reciprocal/count:.4f}")
    else: print("BM25 TRACE: awaiting first live SEC filing index")
    return failures


if __name__=="__main__":
    problems=audit()
    if problems: print("\n".join(problems))
    raise SystemExit(1 if problems else 0)
