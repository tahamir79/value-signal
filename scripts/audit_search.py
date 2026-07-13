from __future__ import annotations

import json, os, re, sys
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


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_index_files(index_path: Path, index: dict) -> list[Path]:
    if index.get("indexMode") != "per_ticker":
        return [index_path]
    root = index_path.parents[2] if index_path.parts[-3:] == ("public", "data", "search_index.json") else Path(".")
    return [root / entry["path"] for _, entry in sorted((index.get("tickers") or {}).items())]


def _search_manifest(index_path: Path, query: str, limit: int = 20, max_tickers: int | None = None) -> list[dict]:
    manifest = _load(index_path)
    if manifest.get("indexMode") != "per_ticker":
        return bm25_search(manifest, query, limit=limit, apply_diversification=False)
    ranked: list[dict] = []
    for ticker_path in _iter_index_files(index_path, manifest)[:max_tickers]:
        if not ticker_path.exists():
            continue
        ranked.extend(bm25_search(_load(ticker_path), query, limit=limit, apply_diversification=False))
    ranked.sort(key=lambda row: (-float(row.get("score", 0)), str(row.get("chunkId") or row.get("id"))))
    return ranked[:limit]


def audit(index_path: Path = Path("public/data/search_index.json"), queries_path: Path = Path("tests/fixtures/retrieval_queries.json")) -> list[str]:
    index=_load(index_path); failures=[]; full_audit=os.getenv("VS_SEARCH_AUDIT_FULL")=="1"; all_index_files=_iter_index_files(index_path,index)
    index_files=all_index_files if full_audit or index.get("indexMode")!="per_ticker" else all_index_files[:25]
    schema3=index.get("schemaVersion")=="3.0.0"; missing=Counter(); tickers=Counter(); forms=Counter(); sections=Counter(); fallback=front_matter=near_duplicates=0
    seen_ticker_ids=set(); lengths=[]; document_count=0
    if index.get("indexMode")=="per_ticker":
        manifest_tickers=index.get("tickers") or {}
        manifest_document_count=sum(int(entry.get("documentCount") or 0) for entry in manifest_tickers.values())
        if index.get("documentCount")!=manifest_document_count: failures.append("manifest document count does not reconcile")
        if index.get("tickerCount")!=len(manifest_tickers): failures.append("manifest ticker count does not reconcile")
    for file_path in index_files:
        if not file_path.exists():
            failures.append(f"missing ticker index: {file_path}")
            continue
        ticker_index=_load(file_path); documents=ticker_index.get("documents",[]); local_lengths=ticker_index.get("documentLengths",[])
        if ticker_index.get("documentCount")!=len(documents) or len(local_lengths)!=len(documents): failures.append(f"{file_path}: index document counts do not reconcile")
        document_count+=len(documents); lengths.extend(local_lengths)
        local_filings=defaultdict(list)
        for row in documents:
            row_id=row.get("id")
            ticker_id=(row.get("ticker"), row_id)
            if ticker_id in seen_ticker_ids: failures.append(f"{row_id}: duplicate chunk ID within ticker {row.get('ticker')}")
            seen_ticker_ids.add(ticker_id)
            absent=CORE-row.keys()
            if schema3: absent|=SCHEMA3-row.keys()
            for key in absent: missing[key]+=1
            if absent: failures.append(f"{row.get('id','?')}: missing metadata {sorted(absent)}")
            if not row.get("text","").strip(): failures.append(f"{row.get('id','?')}: empty chunk")
            url=row.get("sourceUrl") or row.get("url","")
            if not url.startswith("https://www.sec.gov/Archives/"): failures.append(f"{row.get('id','?')}: citation does not resolve to SEC Archives")
            for start,end,name in ((row.get("documentWordStart"),row.get("documentWordEnd"),"word"),(row.get("documentCharStart"),row.get("documentCharEnd"),"character")):
                if start is not None and (not isinstance(start,int) or not isinstance(end,int) or start<0 or end<start): failures.append(f"{row.get('id','?')}: invalid {name} offsets")
            tickers[row.get("ticker","?")]+=1; forms[row.get("formType") or row.get("form","?")]+=1; sections[row.get("sectionKey") or row.get("item","unclassified")]+=1; local_filings[(row.get("ticker"),row.get("accession"))].append(row)
            fallback+=row.get("boundaryType")=="fixed_window_fallback"; front_matter+=not (row.get("sectionKey") or row.get("item"))
            text=row.get("text","").lower()
            if row.get("sectionKey")=="part-iv:item-16" and "signatures" in text: failures.append(f"{row.get('id','?')}: Item 16 contains signatures")
            if str(row.get("sectionKey","")).startswith("preamble:") and re.search(r"(?im)^(?:part|item|signatures?)\b",row.get("text","")): failures.append(f"{row.get('id','?')}: preamble crosses a structural boundary")
            number=str(row.get("itemNumber") or "").lower(); part=str(row.get("part") or "").lower(); form=row.get("formType") or row.get("form")
            if form=="10-K" and number and TEN_K_PARTS.get(number)!=part: failures.append(f"{row.get('id','?')}: invalid 10-K Part/Item mapping")
            if form=="10-Q" and number and (part not in TEN_Q_ITEMS or number not in TEN_Q_ITEMS[part]): failures.append(f"{row.get('id','?')}: invalid 10-Q Part/Item mapping")
        for (ticker,accession),rows in local_filings.items():
            if full_audit:
                near_duplicates+=sum(_jaccard(rows[i].get("text",""),rows[j].get("text",""))>.70 for i in range(len(rows)) for j in range(i+1,len(rows)))
            counts=Counter(row.get("sectionKey") for row in rows)
            if len(rows)>=10 and counts and counts.most_common(1)[0][1]/len(rows)>.75:
                failures.append(f"{ticker}/{accession}: one section owns more than 75% of filing chunks")
    reported_document_count = index.get("documentCount") if index.get("indexMode")=="per_ticker" else document_count
    distribution={"min":min(lengths,default=0),"median":sorted(lengths)[len(lengths)//2] if lengths else 0,"max":max(lengths,default=0)}
    print(f"FILING FETCH/CHUNKS: {'PASS' if reported_document_count else 'AWAITING REFRESH'} ({reported_document_count} chunks, {index.get('tickerCount', len(tickers))} tickers, mode={index.get('indexMode','monolith')}, sampled_files={len(index_files)}/{len(all_index_files)})")
    print(f"SCHEMA/METADATA/CITATIONS: {'PASS' if not failures else 'FAIL'} schema={index.get('schemaVersion')} missing={dict(missing)}")
    print(f"CHUNK DISTRIBUTION: {distribution} fallback_windows={fallback} front_matter={front_matter} near_duplicates={near_duplicates}")
    print(f"BY TICKER SAMPLE: {dict(tickers.most_common(20))}\nBY FORM: {dict(forms)}\nBY SECTION: {dict(sections)}")
    if reported_document_count:
        cases=json.loads(queries_path.read_text(encoding="utf-8")); precision=reciprocal=raw_precision=raw_reciprocal=0.0
        for case in cases:
            ranked=_search_manifest(index_path,case["query"],limit=20,max_tickers=None if full_audit else 30); results=diversify_results(ranked,3)
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
