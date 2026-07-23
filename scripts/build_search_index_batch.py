from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.artifact_paths import ticker_artifact_path
from scripts.build_search_index import (
    SEARCH_SCHEMA_VERSION,
    build_index,
    load_scaled_universe,
    update_bm25_status_artifacts,
    write_compact_json,
)
from scripts.chunk_filings import chunk_filing
from scripts.export_json import write_json
from scripts.models import Security
from scripts.providers.sec_filings import SecFilingProvider
from scripts.text_cleaning import clean_filing_html
from scripts.universe.limits import parse_optional_limit


DEFAULT_MANIFEST = Path("public/data/search_index.json")
DEFAULT_SEARCH_DIR = Path("public/data/search")
DEFAULT_REPORT = Path("data/reports/search_index_batch_report.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def empty_manifest() -> dict[str, Any]:
    generated_at = _now()
    return {
        "schemaVersion": SEARCH_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "corpusHash": hashlib.sha256(b"").hexdigest(),
        "status": "not_run",
        "indexMode": "per_ticker",
        "batchAware": True,
        "documentCount": 0,
        "termCount": 0,
        "tickerCount": 0,
        "tickers": {},
        "errors": [],
        "lastBatch": None,
    }


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    payload = _read_json(path)
    if not payload or payload.get("indexMode") != "per_ticker":
        return empty_manifest()
    payload.setdefault("schemaVersion", SEARCH_SCHEMA_VERSION)
    payload.setdefault("tickers", {})
    payload.setdefault("errors", [])
    payload["batchAware"] = True
    return payload


def indexed_tickers(manifest: dict[str, Any]) -> set[str]:
    tickers = manifest.get("tickers") or {}
    return {str(ticker).upper() for ticker, entry in tickers.items() if isinstance(entry, dict) and entry.get("documentCount", 0) > 0}


def attempted_tickers(manifest: dict[str, Any]) -> set[str]:
    attempted = set(indexed_tickers(manifest))
    for error in manifest.get("errors") or []:
        ticker = str(error.get("ticker") or "").upper()
        if ticker:
            attempted.add(ticker)
    return attempted


def select_batch(
    securities: list[Security],
    manifest: dict[str, Any],
    *,
    batch_size: int,
    batch_index: int | None = None,
    tickers: Iterable[str] | None = None,
    force: bool = False,
) -> list[Security]:
    wanted = {ticker.upper() for ticker in tickers or []}
    if wanted:
        candidates = [security for security in securities if security.ticker.upper() in wanted]
    elif batch_index is not None:
        start = batch_index * batch_size
        candidates = securities[start:start + batch_size]
    else:
        candidates = securities
    if not force:
        attempted = attempted_tickers(manifest)
        candidates = [security for security in candidates if security.ticker.upper() not in attempted]
    return candidates[:batch_size]


def index_security(security: Security, provider: SecFilingProvider, *, per_form: int) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    chunks: list[dict[str, Any]] = []
    try:
        filings = provider.fetch_recent(security.ticker, security.cik, per_form)
        for filing in filings:
            filing_chunks = chunk_filing(filing, clean_filing_html(filing.html))
            for chunk in filing_chunks:
                chunk["companyName"] = security.company_name
            chunks.extend(filing_chunks)
        if not chunks:
            return None, {"ticker": security.ticker, "message": "NO_SEARCHABLE_FILING_CHUNKS"}
        return build_index(chunks), None
    except Exception as exc:
        return None, {"ticker": security.ticker, "message": f"{type(exc).__name__}: {exc}"}


def _manifest_hash(tickers: dict[str, dict[str, Any]]) -> str:
    lines = [
        f"{ticker}:{entry.get('documentCount', 0)}:{entry.get('latestFilingDate') or ''}:{entry.get('path') or ''}"
        for ticker, entry in sorted(tickers.items())
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def merge_ticker_index(
    manifest: dict[str, Any],
    *,
    ticker: str,
    ticker_index: dict[str, Any],
    search_dir: Path = DEFAULT_SEARCH_DIR,
) -> dict[str, Any]:
    ticker = ticker.upper()
    ticker_path = ticker_artifact_path(search_dir, ticker)
    write_compact_json(ticker_path, ticker_index)
    filing_dates = [row.get("filingDate") for row in ticker_index.get("documents", []) if row.get("filingDate")]
    manifest.setdefault("tickers", {})[ticker] = {
        "path": str(ticker_path.as_posix()),
        "documentCount": ticker_index.get("documentCount", 0),
        "termCount": len(ticker_index.get("postings", {})),
        "latestFilingDate": max(filing_dates) if filing_dates else None,
    }
    return manifest


def finalize_manifest(manifest: dict[str, Any], *, batch: dict[str, Any], errors: list[dict[str, str]]) -> dict[str, Any]:
    tickers = manifest.get("tickers") or {}
    existing_errors = [
        error for error in manifest.get("errors", [])
        if str(error.get("ticker") or "").upper() not in {str(item.get("ticker") or "").upper() for item in errors}
    ]
    manifest["generatedAt"] = _now()
    manifest["corpusHash"] = _manifest_hash(tickers)
    manifest["status"] = "partial_success" if errors or existing_errors else "success"
    manifest["indexMode"] = "per_ticker"
    manifest["batchAware"] = True
    manifest["documentCount"] = sum(int(entry.get("documentCount", 0)) for entry in tickers.values())
    manifest["termCount"] = sum(int(entry.get("termCount", 0)) for entry in tickers.values())
    manifest["tickerCount"] = len(tickers)
    manifest["errors"] = existing_errors + errors
    manifest["lastBatch"] = batch
    return manifest


def build_search_index_batch(
    *,
    universe: Path,
    output: Path = DEFAULT_MANIFEST,
    search_dir: Path = DEFAULT_SEARCH_DIR,
    report_path: Path = DEFAULT_REPORT,
    limit: int | None = None,
    batch_size: int = 25,
    batch_index: int | None = None,
    tickers: list[str] | None = None,
    per_form: int = 1,
    force: bool = False,
    update_status: bool = True,
    user_agent: str,
) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero")
    securities = load_scaled_universe(universe, limit)
    manifest = load_manifest(output)
    selected = select_batch(securities, manifest, batch_size=batch_size, batch_index=batch_index, tickers=tickers, force=force)
    provider = SecFilingProvider(user_agent)
    errors: list[dict[str, str]] = []
    indexed: list[str] = []
    for security in selected:
        ticker_index, error = index_security(security, provider, per_form=per_form)
        if ticker_index and ticker_index.get("documentCount", 0) > 0:
            merge_ticker_index(manifest, ticker=security.ticker, ticker_index=ticker_index, search_dir=search_dir)
            indexed.append(security.ticker)
            manifest = finalize_manifest(
                manifest,
                batch={
                    "selectedTickers": [item.ticker for item in selected],
                    "indexedTickers": indexed,
                    "failedTickers": [item["ticker"] for item in errors],
                    "batchSize": batch_size,
                    "batchIndex": batch_index,
                    "force": force,
                    "finished": False,
                },
                errors=errors,
            )
            write_json(output, manifest)
        if error:
            errors.append(error)
    batch = {
        "generatedAt": _now(),
        "universe": str(universe),
        "batchSize": batch_size,
        "batchIndex": batch_index,
        "force": force,
        "selectedTickers": [item.ticker for item in selected],
        "indexedTickers": indexed,
        "failedTickers": [item["ticker"] for item in errors],
        "requested": len(selected),
        "indexed": len(indexed),
        "failed": len(errors),
        "remainingUnindexed": max(0, len([security for security in securities if security.ticker.upper() not in indexed_tickers(manifest)])),
        "remainingUnattempted": max(0, len([
            security for security in securities
            if security.ticker.upper() not in (attempted_tickers(manifest) | {str(error.get("ticker") or "").upper() for error in errors})
        ])),
        "finished": True,
    }
    manifest = finalize_manifest(manifest, batch=batch, errors=errors)
    write_json(output, manifest)
    if update_status:
        update_bm25_status_artifacts(output.parent, manifest)
    report = {
        "schemaVersion": SEARCH_SCHEMA_VERSION,
        "status": "success" if not errors else "partial_success",
        "manifest": str(output),
        "searchDir": str(search_dir),
        "manifestTickerCount": manifest.get("tickerCount", 0),
        "manifestDocumentCount": manifest.get("documentCount", 0),
        "batch": batch,
        "errors": errors,
    }
    write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Incrementally populate per-ticker ValueSignal BM25 filing indexes.")
    parser.add_argument("--universe", type=Path, default=Path("data/universe/universe.json"))
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--search-dir", type=Path, default=DEFAULT_SEARCH_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=parse_optional_limit)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--batch-index", type=int)
    parser.add_argument("--tickers", nargs="*")
    parser.add_argument("--per-form", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-status-update", action="store_true")
    args = parser.parse_args()
    user_agent = os.getenv("VS_USER_AGENT", "")
    if not user_agent or "@" not in user_agent:
        print("VS_USER_AGENT must identify the application and include a contact email.", file=sys.stderr)
        return 2
    report = build_search_index_batch(
        universe=args.universe,
        output=args.output,
        search_dir=args.search_dir,
        report_path=args.report,
        limit=args.limit,
        batch_size=args.batch_size,
        batch_index=args.batch_index,
        tickers=args.tickers,
        per_form=args.per_form,
        force=args.force,
        update_status=not args.no_status_update,
        user_agent=user_agent,
    )
    print(json.dumps(report["batch"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
