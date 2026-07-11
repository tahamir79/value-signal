from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.chunk_filings import chunk_filing
from scripts.providers.sec_filings import FilingDocument
from scripts.sec.sec_client import SecClient
from scripts.text_cleaning import clean_filing_html
from scripts.universe.normalize_symbols import normalize_cik, normalize_ticker
from scripts.universe.universe_manifest import utc_now


SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_path}/{primary_document}"


@dataclass(frozen=True)
class IngestPaths:
    root: Path

    @property
    def raw_html(self) -> Path:
        return self.root / "cache" / "sec" / "filings" / "raw_html"

    @property
    def clean_text(self) -> Path:
        return self.root / "cache" / "sec" / "filings" / "clean_text"

    @property
    def chunks(self) -> Path:
        return self.root / "cache" / "sec" / "filings" / "chunks"

    @property
    def metadata(self) -> Path:
        return self.root / "filings"

    @property
    def reports(self) -> Path:
        return self.root / "reports"


def load_universe(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("records") or payload
    if not isinstance(rows, list):
        raise ValueError("universe must be a list or an object with records")
    return rows


def filter_universe(rows: list[dict[str, Any]], *, ticker: str | None = None,
                    tickers: list[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    wanted = {normalize_ticker(value) for value in (tickers or [])}
    if ticker:
        wanted.add(normalize_ticker(ticker))
    filtered = [row for row in rows if row.get("isSupported", True)]
    if wanted:
        filtered = [row for row in filtered if normalize_ticker(row.get("ticker")) in wanted]
    return filtered[:limit] if limit else filtered


def discover_filings(submissions: dict[str, Any], *, forms: list[str], per_form: int = 1,
                     since: str | None = None) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    counts = {form.upper(): 0 for form in forms}
    rows: list[dict[str, Any]] = []
    for index, form in enumerate(recent.get("form", [])):
        form = str(form).upper()
        if form not in counts or counts[form] >= per_form:
            continue
        filing_date = _recent_value(recent, "filingDate", index)
        if since and filing_date and filing_date < since:
            continue
        accession = _recent_value(recent, "accessionNumber", index)
        primary = _recent_value(recent, "primaryDocument", index)
        if not accession or not primary:
            continue
        counts[form] += 1
        rows.append({
            "formType": form,
            "filingDate": filing_date,
            "reportDate": _recent_value(recent, "reportDate", index),
            "accession": accession,
            "primaryDocument": primary,
        })
    return rows


def _recent_value(recent: dict[str, Any], key: str, index: int) -> str | None:
    values = recent.get(key) or []
    try:
        value = values[index]
    except IndexError:
        return None
    return str(value) if value is not None else None


def filing_metadata(row: dict[str, Any], filing: dict[str, Any], paths: IngestPaths) -> dict[str, Any]:
    cik = normalize_cik(row["cik"])
    ticker = normalize_ticker(row["ticker"])
    accession = filing["accession"]
    accession_path = accession.replace("-", "")
    primary = filing["primaryDocument"]
    url = ARCHIVES_URL.format(cik_int=int(cik), accession_path=accession_path, primary_document=primary)
    stem = f"{ticker}_{filing['formType']}_{filing['filingDate']}_{accession_path}"
    return {
        "cik": cik,
        "ticker": ticker,
        "companyName": row.get("companyName") or row.get("name") or ticker,
        "formType": filing["formType"],
        "filingDate": filing["filingDate"],
        "reportDate": filing.get("reportDate"),
        "accession": accession,
        "primaryDocument": primary,
        "filingDetailUrl": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/",
        "documentUrl": url,
        "localRawPath": str(paths.raw_html / f"{stem}.html"),
        "localCleanPath": str(paths.clean_text / f"{stem}.txt"),
        "localChunkPath": str(paths.chunks / f"{stem}.json"),
        "status": "pending",
        "error": None,
    }


def ingest_company(row: dict[str, Any], *, client: SecClient, paths: IngestPaths, forms: list[str],
                   per_form: int, since: str | None, force: bool, dry_run: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cik = normalize_cik(row["cik"])
    ticker = normalize_ticker(row["ticker"])
    submissions_url = SUBMISSIONS_URL.format(cik=cik)
    submissions, _ = client.get_json(submissions_url, force=force)
    filings = discover_filings(submissions, forms=forms, per_form=per_form, since=since)
    metadata_rows: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for filing in filings:
        meta = filing_metadata(row, filing, paths)
        try:
            metadata_rows.append(meta)
            if dry_run:
                meta["status"] = "skipped"
                continue
            raw_path = Path(meta["localRawPath"])
            clean_path = Path(meta["localCleanPath"])
            chunk_path = Path(meta["localChunkPath"])
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            clean_path.parent.mkdir(parents=True, exist_ok=True)
            chunk_path.parent.mkdir(parents=True, exist_ok=True)
            if raw_path.exists() and not force:
                html = raw_path.read_text(encoding="utf-8", errors="replace")
            else:
                body, _ = client.get_bytes(meta["documentUrl"], force=force)
                html = body.decode("utf-8", errors="replace")
                raw_path.write_text(html, encoding="utf-8")
            clean = clean_filing_html(html)
            clean_path.write_text(clean, encoding="utf-8")
            document = FilingDocument(ticker, cik, meta["accession"], meta["filingDate"], meta.get("reportDate") or "",
                                      meta["formType"], meta["primaryDocument"], meta["documentUrl"], html)
            filing_chunks = chunk_filing(document, clean)
            for chunk in filing_chunks:
                chunk["companyName"] = meta["companyName"]
                chunk["sourcePath"] = str(clean_path)
            chunk_path.write_text(json.dumps({"records": filing_chunks}, indent=2) + "\n", encoding="utf-8")
            chunks.extend(filing_chunks)
            meta["status"] = "chunked"
        except Exception as exc:
            meta["status"] = "failed"
            meta["error"] = f"{type(exc).__name__}: {exc}"
            failures.append({"ticker": ticker, "cik": cik, "companyName": meta["companyName"],
                             "stage": "filing_ingestion", "error": meta["error"], "retryCount": 0,
                             "timestamp": utc_now()})
    return metadata_rows, chunks, failures


def write_outputs(metadata: list[dict[str, Any]], chunks: list[dict[str, Any]], failures: list[dict[str, Any]],
                  *, paths: IngestPaths, dry_run: bool) -> None:
    if dry_run:
        return
    paths.metadata.mkdir(parents=True, exist_ok=True)
    paths.chunks.mkdir(parents=True, exist_ok=True)
    paths.reports.mkdir(parents=True, exist_ok=True)
    (paths.metadata / "filing_metadata.json").write_text(json.dumps({"records": metadata}, indent=2) + "\n", encoding="utf-8")
    (paths.chunks / "all_chunks.json").write_text(json.dumps({"records": chunks}, indent=2) + "\n", encoding="utf-8")
    (paths.reports / "filing_failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover, download, clean, and chunk SEC filings for a staged universe.")
    parser.add_argument("--universe", default="data/universe/universe.json")
    parser.add_argument("--forms", nargs="*", default=["10-K", "10-Q"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ticker")
    parser.add_argument("--tickers", nargs="*")
    parser.add_argument("--since")
    parser.add_argument("--per-form", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--sleep-ms", type=int, default=200)
    parser.add_argument("--output-dir", default="data")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    user_agent = os.getenv("VS_USER_AGENT") or os.getenv("SEC_USER_AGENT")
    if not user_agent:
        print("Set VS_USER_AGENT with an identifying contact before SEC filing ingestion.", file=sys.stderr)
        return 2
    paths = IngestPaths(Path(args.output_dir))
    rows = filter_universe(load_universe(Path(args.universe)), ticker=args.ticker, tickers=args.tickers, limit=args.limit)
    client = SecClient(user_agent=user_agent, cache_dir=Path(args.output_dir) / "cache" / "sec" / "http", sleep_ms=args.sleep_ms)
    metadata: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for row in rows:
        try:
            meta_rows, filing_chunks, filing_failures = ingest_company(row, client=client, paths=paths, forms=[form.upper() for form in args.forms],
                                                                       per_form=args.per_form, since=args.since, force=args.force, dry_run=args.dry_run)
            metadata.extend(meta_rows)
            chunks.extend(filing_chunks)
            failures.extend(filing_failures)
        except Exception as exc:
            failures.append({"ticker": row.get("ticker"), "cik": row.get("cik"), "companyName": row.get("companyName"),
                             "stage": "submissions_discovery", "error": f"{type(exc).__name__}: {exc}",
                             "retryCount": 0, "timestamp": utc_now()})
    write_outputs(metadata, chunks, failures, paths=paths, dry_run=args.dry_run)
    report = {
        "runId": f"filings-{utc_now()}",
        "startedAt": utc_now(),
        "endedAt": utc_now(),
        "companiesAttempted": len(rows),
        "filingsDiscovered": len(metadata),
        "filingsChunked": sum(1 for row in metadata if row["status"] == "chunked"),
        "chunksCreated": len(chunks),
        "companiesFailed": len({failure.get("ticker") for failure in failures}),
        "failures": failures,
        "dryRun": args.dry_run,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
