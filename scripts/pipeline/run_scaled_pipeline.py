from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.filings.ingest_filings import IngestPaths, filter_universe, ingest_company
from scripts.sec.sec_client import SecClient
from scripts.universe.build_universe import build_scaled_universe, write_universe
from scripts.universe.universe_manifest import utc_now


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a staged, restartable ValueSignal scaling pipeline.")
    parser.add_argument("--mode", default="starter")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ticker")
    parser.add_argument("--tickers", nargs="*")
    parser.add_argument("--forms", nargs="*", default=["10-K", "10-Q"])
    parser.add_argument("--since")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--sleep-ms", type=int, default=200)
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--ingest-filings", action="store_true")
    parser.add_argument("--per-form", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = time.time()
    run_id = f"scaled-{int(started)}"
    output_dir = Path(args.output_dir)
    universe_dir = output_dir / "universe"
    report_dir = output_dir / "reports"
    rows = build_scaled_universe(mode=args.mode, limit=args.limit)
    manifest = write_universe(rows, mode=args.mode, limit=args.limit, output_dir=universe_dir, dry_run=args.dry_run)
    supported = [row for row in rows if row.get("isSupported")]
    metadata: list[dict] = []
    chunks: list[dict] = []
    failures: list[dict] = []
    if args.ingest_filings:
        user_agent = os.getenv("VS_USER_AGENT") or os.getenv("SEC_USER_AGENT")
        if not user_agent:
            raise RuntimeError("Set VS_USER_AGENT with an identifying contact before SEC filing ingestion.")
        client = SecClient(user_agent=user_agent, cache_dir=output_dir / "cache" / "sec" / "http", sleep_ms=args.sleep_ms)
        paths = IngestPaths(output_dir)
        for row in filter_universe(rows, ticker=args.ticker, tickers=args.tickers, limit=args.limit):
            try:
                meta_rows, filing_chunks, filing_failures = ingest_company(
                    row,
                    client=client,
                    paths=paths,
                    forms=[form.upper() for form in args.forms],
                    per_form=args.per_form,
                    since=args.since,
                    force=args.force,
                    dry_run=args.dry_run,
                )
                metadata.extend(meta_rows)
                chunks.extend(filing_chunks)
                failures.extend(filing_failures)
            except Exception as exc:
                failures.append({"ticker": row.get("ticker"), "cik": row.get("cik"), "companyName": row.get("companyName"),
                                 "stage": "filing_ingestion", "error": f"{type(exc).__name__}: {exc}",
                                 "retryCount": 0, "timestamp": utc_now()})
    report = {
        "runId": run_id,
        "startedAt": utc_now(),
        "endedAt": utc_now(),
        "durationSeconds": round(time.time() - started, 3),
        "universeMode": args.mode,
        "requestedLimit": args.limit,
        "companiesAttempted": len(supported),
        "companiesSucceeded": len(supported) - len({failure.get("ticker") for failure in failures}),
        "companiesFailed": len({failure.get("ticker") for failure in failures}),
        "filingsDownloaded": sum(1 for row in metadata if row.get("status") in {"chunked", "cleaned", "downloaded"}),
        "filingsCleaned": 0,
        "filingsChunked": sum(1 for row in metadata if row.get("status") == "chunked"),
        "chunksCreated": len(chunks),
        "searchIndexBuilt": False,
        "scoringRun": False,
        "embeddingRun": False,
        "warnings": [] if args.ingest_filings else ["Scaling foundation run only: filing ingestion/scoring are staged next."],
        "failures": failures,
        "universeManifest": manifest,
    }
    if not args.dry_run:
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "pipeline_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (report_dir / "failures.json").write_text(json.dumps([], indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
