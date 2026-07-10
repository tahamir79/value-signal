from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

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
    report = {
        "runId": run_id,
        "startedAt": utc_now(),
        "endedAt": utc_now(),
        "durationSeconds": round(time.time() - started, 3),
        "universeMode": args.mode,
        "requestedLimit": args.limit,
        "companiesAttempted": len(supported),
        "companiesSucceeded": len(supported),
        "companiesFailed": 0,
        "filingsDownloaded": 0,
        "filingsCleaned": 0,
        "filingsChunked": 0,
        "chunksCreated": 0,
        "searchIndexBuilt": False,
        "scoringRun": False,
        "embeddingRun": False,
        "warnings": ["Scaling foundation run only: filing ingestion/scoring are staged next."],
        "failures": [],
        "universeManifest": manifest,
    }
    if not args.dry_run:
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "pipeline_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (report_dir / "failures.json").write_text(json.dumps([], indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
