from __future__ import annotations

import argparse
import hashlib
import json
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
from scripts.artifact_paths import ticker_artifact_path, ticker_from_artifact_stem
from scripts.models import Security
from scripts.providers.sec_filings import SecFilingProvider
from scripts.retrieval import diversify_results
from scripts.text_cleaning import clean_filing_html
from scripts.universe.limits import parse_optional_limit

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


def load_scaled_universe(path: Path, limit: int | None = None) -> list[Security]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("records") or payload
    if not isinstance(rows, list):
        raise ValueError("Universe file must contain a list or records array")
    securities: list[Security] = []
    for row in rows:
        if not row.get("isSupported", True):
            continue
        securities.append(Security(
            row["ticker"],
            row["cik"],
            row.get("companyName") or row.get("name") or row["ticker"],
            row.get("exchange") or "UNKNOWN",
            row.get("sector") or "Unknown",
        ))
        if limit and len(securities) >= limit:
            break
    if len({security.ticker for security in securities}) != len(securities):
        raise ValueError("Universe contains duplicate tickers")
    return securities


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _mark_status(status: dict[str, Any], *, indexed: bool, latest_filing_date: str | None) -> bool:
    updates = {
        "filingsDownloaded": indexed,
        "filingsCleaned": indexed,
        "filingsChunked": indexed,
        "bm25Indexed": indexed,
    }
    changed = any(status.get(key) != value for key, value in updates.items())
    status.update(updates)
    return changed


def update_bm25_status_artifacts(data_dir: Path, index: dict[str, Any]) -> dict[str, Any]:
    latest_by_ticker: dict[str, str] = {}
    if index.get("indexMode") == "per_ticker" and isinstance(index.get("tickers"), dict):
        for ticker, entry in index["tickers"].items():
            normalized = str(ticker).upper()
            if normalized:
                latest_by_ticker[normalized] = entry.get("latestFilingDate")
    else:
        for document in index.get("documents", []):
            ticker = str(document.get("ticker") or "").upper()
            filing_date = document.get("filingDate")
            if not ticker:
                continue
            if filing_date and filing_date > latest_by_ticker.get(ticker, ""):
                latest_by_ticker[ticker] = filing_date
    indexed_tickers = set(latest_by_ticker)

    def apply_to_records(payload: dict[str, Any] | None, ticker_getter: Any) -> bool:
        if not payload or not isinstance(payload.get("records"), list):
            return False
        changed = False
        for row in payload["records"]:
            ticker = str(ticker_getter(row) or "").upper()
            status = row.get("dataStatus")
            if isinstance(status, dict):
                changed = _mark_status(status, indexed=ticker in indexed_tickers, latest_filing_date=latest_by_ticker.get(ticker)) or changed
        return changed

    dashboard = _read_json(data_dir / "dashboard.json")
    if apply_to_records(dashboard, lambda row: row.get("security", {}).get("ticker")):
        write_json(data_dir / "dashboard.json", dashboard or {})

    summary = _read_json(data_dir / "stocks" / "summary.json")
    if apply_to_records(summary, lambda row: row.get("ticker")):
        write_json(data_dir / "stocks" / "summary.json", summary or {})

    etl_report = _read_json(data_dir / "etl_report.json")
    if etl_report and isinstance(etl_report.get("tickers"), list):
        changed = False
        for row in etl_report["tickers"]:
            ticker = str(row.get("ticker") or "").upper()
            status = row.get("dataStatus")
            if isinstance(status, dict):
                changed = _mark_status(status, indexed=ticker in indexed_tickers, latest_filing_date=latest_by_ticker.get(ticker)) or changed
        if changed:
            write_json(data_dir / "etl_report.json", etl_report)

    stocks_dir = data_dir / "stocks"
    if stocks_dir.exists():
        for stock_path in stocks_dir.glob("*.json"):
            if stock_path.name == "summary.json":
                continue
            payload = _read_json(stock_path)
            record = (payload or {}).get("record", payload or {})
            ticker = str(record.get("security", {}).get("ticker") or ticker_from_artifact_stem(stock_path.stem)).upper()
            status = record.get("dataStatus")
            if isinstance(status, dict):
                if _mark_status(status, indexed=ticker in indexed_tickers, latest_filing_date=latest_by_ticker.get(ticker)):
                    write_json(stock_path, payload or {})

    coverage = _read_json(data_dir / "universe_coverage_report.json")
    if coverage and isinstance(coverage.get("counts"), dict):
        counts = coverage["counts"]
        counts["filings_downloaded"] = len(indexed_tickers)
        counts["filings_indexed"] = len(indexed_tickers)
        counts["searchable_companies"] = len(indexed_tickers)
        write_json(data_dir / "universe_coverage_report.json", coverage)

    return {"indexedTickers": sorted(indexed_tickers), "indexedTickerCount": len(indexed_tickers)}


def write_compact_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_partitioned_index(index: dict[str, Any], manifest_path: Path, search_dir: Path) -> dict[str, Any]:
    search_dir.mkdir(parents=True, exist_ok=True)
    documents_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in index.get("documents", []):
        ticker = str(document.get("ticker") or "").upper()
        if ticker:
            documents_by_ticker[ticker].append(document)

    tickers: dict[str, dict[str, Any]] = {}
    for ticker, documents in sorted(documents_by_ticker.items()):
        unique_documents: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for document in documents:
            document_id = str(document.get("chunkId") or document.get("id"))
            if document_id in seen_ids:
                continue
            seen_ids.add(document_id)
            unique_documents.append(document)
        ticker_index = build_index(unique_documents)
        ticker_path = ticker_artifact_path(search_dir, ticker)
        write_compact_json(ticker_path, ticker_index)
        filing_dates = [row.get("filingDate") for row in unique_documents if row.get("filingDate")]
        tickers[ticker] = {
            "path": str(ticker_path.as_posix()),
            "documentCount": ticker_index["documentCount"],
            "termCount": len(ticker_index["postings"]),
            "latestFilingDate": max(filing_dates) if filing_dates else None,
        }

    manifest = {
        "schemaVersion": SEARCH_SCHEMA_VERSION,
        "generatedAt": index.get("generatedAt"),
        "corpusHash": index.get("corpusHash"),
        "status": index.get("status"),
        "indexMode": "per_ticker",
        "documentCount": sum(row["documentCount"] for row in tickers.values()),
        "termCount": len(index.get("postings", {})),
        "tickerCount": len(tickers),
        "tickers": tickers,
        "errors": index.get("errors", []),
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the ValueSignal SEC filing search index")
    parser.add_argument("--output", type=Path, default=Path("public/data/search_index.json"))
    parser.add_argument("--universe", type=Path, help="Optional scaled universe JSON file with records containing ticker, cik, and companyName")
    parser.add_argument("--limit", type=parse_optional_limit)
    parser.add_argument("--per-form", type=int, default=1)
    parser.add_argument("--search-dir", type=Path, help="Directory for per-ticker BM25 index files. Defaults to public/data/search.")
    parser.add_argument("--monolith", action="store_true", help="Write one large search_index.json instead of a manifest plus per-ticker indexes")
    parser.add_argument("--no-status-update", action="store_true", help="Only write search_index.json; do not back-fill bm25Indexed status flags")
    args = parser.parse_args()
    user_agent = os.getenv("VS_USER_AGENT", "")
    if not user_agent or "@" not in user_agent:
        print("VS_USER_AGENT must identify the application and include a contact email.", file=sys.stderr)
        return 2
    provider = SecFilingProvider(user_agent)
    chunks, errors = [], []
    securities = load_scaled_universe(args.universe, args.limit) if args.universe else build_universe(args.limit)
    for security in securities:
        try:
            for filing in provider.fetch_recent(security.ticker, security.cik, args.per_form):
                filing_chunks = chunk_filing(filing, clean_filing_html(filing.html))
                for chunk in filing_chunks:
                    chunk["companyName"] = security.company_name
                chunks.extend(filing_chunks)
        except Exception as exc:
            errors.append({"ticker": security.ticker, "message": f"{type(exc).__name__}: {exc}"})
    index = build_index(chunks, errors)
    if args.monolith:
        write_json(args.output, index)
        output = index
    else:
        output = write_partitioned_index(index, args.output, args.search_dir or args.output.parent / "search")
    status = None if args.no_status_update else update_bm25_status_artifacts(args.output.parent, index)
    suffix = f", {status['indexedTickerCount']} tickers indexed" if status else ""
    print(f"Search index {output['status']}: {output['documentCount']} chunks, {len(index['postings'])} terms{suffix}")
    return 0 if index["documentCount"] else 1


if __name__ == "__main__": raise SystemExit(main())
