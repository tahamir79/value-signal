from __future__ import annotations

import argparse
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.export_json import write_json
from scripts.models import PriceBar, Security, record
from scripts.providers.price_provider import FixturePriceProvider, PriceProvider, YahooChartPriceProvider
from scripts.providers.sec_companyfacts import CompanyFactsProvider, FixtureCompanyFactsProvider, SecCompanyFactsProvider
from scripts.providers.http import ProviderError
from scripts.run_etl import _load_universe_records, _securities_from_universe_file, run
from scripts.universe.limits import parse_optional_limit, parse_optional_offset


SCHEMA_VERSION = "1.0.0"
DEFAULT_BATCH_SIZE = 100
DEFAULT_CHECKPOINT_DIR = Path("data/checkpoints/etl_raw")
BENCHMARK_TICKER = "SPY"


def required_user_agent() -> str:
    user_agent = os.getenv("VS_USER_AGENT") or os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise RuntimeError("Set VS_USER_AGENT with an identifying contact before provider requests.")
    return user_agent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def checkpoint_path(checkpoint_dir: Path, start: int, end: int) -> Path:
    return checkpoint_dir / f"batch_{start:05d}_{end:05d}.json"


def checkpoint_status_path(checkpoint_dir: Path, start: int, end: int) -> Path:
    return checkpoint_dir / f"batch_{start:05d}_{end:05d}.status.json"


def benchmark_checkpoint_path(checkpoint_dir: Path) -> Path:
    return checkpoint_dir / f"benchmark_{BENCHMARK_TICKER}.json"


def batch_checkpoint_paths(checkpoint_dir: Path) -> list[Path]:
    if not checkpoint_dir.exists():
        return []
    return sorted(path for path in checkpoint_dir.glob("batch_*.json") if not path.name.endswith(".status.json"))


def security_from_record(payload: dict[str, Any]) -> Security:
    return Security(
        str(payload["ticker"]),
        str(payload["cik"]),
        str(payload.get("company_name") or payload.get("companyName") or payload.get("name") or payload["ticker"]),
        str(payload.get("exchange") or "UNKNOWN"),
        str(payload.get("sector") or "Unknown"),
    )


def price_from_record(payload: dict[str, Any]) -> PriceBar:
    return PriceBar(
        ticker=str(payload["ticker"]),
        date=str(payload["date"]),
        open=float(payload["open"]),
        high=float(payload["high"]),
        low=float(payload["low"]),
        close=float(payload["close"]),
        volume=int(payload["volume"]),
        source=str(payload["source"]),
        adjusted_close=float(payload["adjusted_close"]) if payload.get("adjusted_close") is not None else None,
    )


def supported_securities(universe_path: Path, *, limit: int | None = None, offset: int = 0) -> list[Security]:
    return _securities_from_universe_file(universe_path, limit=limit, offset=offset)


def fetch_benchmark_checkpoint(price_provider: PriceProvider, checkpoint_dir: Path, *, force: bool = False) -> dict[str, Any]:
    path = benchmark_checkpoint_path(checkpoint_dir)
    if path.exists() and not force:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cacheHit"] = True
        return payload
    began = perf_counter()
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    try:
        prices = price_provider.fetch(BENCHMARK_TICKER)
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "benchmark_price_checkpoint",
            "ticker": BENCHMARK_TICKER,
            "generatedAt": utc_now(),
            "status": "success",
            "priceRows": [record(price) for price in prices],
            "error": None,
            "durationMs": round((perf_counter() - began) * 1000),
            "cacheHit": False,
        }
    except Exception as exc:
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "benchmark_price_checkpoint",
            "ticker": BENCHMARK_TICKER,
            "generatedAt": utc_now(),
            "status": "failed",
            "priceRows": [],
            "error": f"{type(exc).__name__}: {exc}",
            "durationMs": round((perf_counter() - began) * 1000),
            "cacheHit": False,
        }
    write_json(path, payload)
    return payload


def fetch_batch_checkpoint(
    *,
    securities: list[Security],
    batch_index: int,
    start: int,
    end: int,
    checkpoint_dir: Path,
    price_provider: PriceProvider,
    facts_provider: CompanyFactsProvider,
    force: bool = False,
    progress: bool = True,
    max_workers: int = 1,
) -> dict[str, Any]:
    path = checkpoint_path(checkpoint_dir, start, end)
    if path.exists() and not force:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if is_complete_batch_payload(payload):
            payload["cacheHit"] = True
            return payload
        rows = list(payload.get("records", []))
        errors = list(payload.get("errors", []))
        resumed_from_partial = True
    else:
        rows = []
        errors = []
        resumed_from_partial = False

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    began = perf_counter()
    processed = {
        str(row.get("security", {}).get("ticker", "")).upper()
        for row in rows
        if row.get("security")
    } | {str(error.get("ticker", "")).upper() for error in errors}

    def status_payload(status: str) -> dict[str, Any]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "kind": "raw_etl_batch_checkpoint",
            "status": status,
            "generatedAt": utc_now(),
            "batchIndex": batch_index,
            "startOffset": start,
            "endOffsetExclusive": end,
            "attemptedTickers": len(securities),
            "processedTickers": len(processed),
            "successfulTickers": len(rows),
            "failedTickers": len(errors),
            "durationMs": round((perf_counter() - began) * 1000),
            "cacheHit": False,
            "resumedFromPartial": resumed_from_partial,
            "maxWorkers": max_workers,
            "completedTickers": sorted(processed),
            "errorTickers": [str(error.get("ticker", "")).upper() for error in errors],
        }

    def write_progress(status: str) -> None:
        summary = status_payload(status)
        write_json(path, {
            **summary,
            "records": rows,
            "errors": errors,
        })
        write_json(checkpoint_status_path(checkpoint_dir, start, end), summary)

    def fetch_one(security: Security) -> tuple[Security, dict[str, Any] | None, dict[str, Any] | None]:
        ticker_started = perf_counter()
        try:
            prices = price_provider.fetch(security.ticker)
            company_facts = facts_provider.fetch(security.cik)
            return security, {
                "security": record(security),
                "priceRows": [record(price) for price in prices],
                "companyFacts": company_facts,
                "durationMs": round((perf_counter() - ticker_started) * 1000),
            }, None
        except Exception as exc:
            return security, None, {
                "ticker": security.ticker,
                "cik": security.cik,
                "companyName": security.company_name,
                "stage": "raw_provider_fetch",
                "message": f"{type(exc).__name__}: {exc}",
                "durationMs": round((perf_counter() - ticker_started) * 1000),
            }

    remaining = [security for security in securities if security.ticker not in processed]
    worker_count = max(1, min(max_workers, len(remaining) or 1))

    def record_result(security: Security, row: dict[str, Any] | None, error: dict[str, Any] | None) -> None:
        if row is not None:
            rows.append(row)
        if error is not None:
            errors.append(error)
        processed.add(security.ticker)
        write_progress("partial")
        if progress:
            print(json.dumps({
                "batchIndex": batch_index,
                "ticker": security.ticker,
                "startOffset": start,
                "endOffsetExclusive": end,
                "processedTickers": len(processed),
                "attemptedTickers": len(securities),
                "successfulTickers": len(rows),
                "failedTickers": len(errors),
                "status": "partial",
                "maxWorkers": worker_count,
            }, sort_keys=True), flush=True)

    if worker_count == 1:
        for security in remaining:
            record_result(*fetch_one(security))
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(fetch_one, security) for security in remaining]
            for future in as_completed(futures):
                record_result(*future.result())

    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "raw_etl_batch_checkpoint",
        "status": "complete",
        "generatedAt": utc_now(),
        "batchIndex": batch_index,
        "startOffset": start,
        "endOffsetExclusive": end,
        "attemptedTickers": len(securities),
        "processedTickers": len(processed),
        "successfulTickers": len(rows),
        "failedTickers": len(errors),
        "records": rows,
        "errors": errors,
        "durationMs": round((perf_counter() - began) * 1000),
        "cacheHit": False,
        "resumedFromPartial": resumed_from_partial,
        "maxWorkers": max_workers,
    }
    write_json(path, payload)
    write_json(checkpoint_status_path(checkpoint_dir, start, end), status_payload("complete"))
    return payload


def iter_batches(securities: list[Security], batch_size: int) -> list[tuple[int, int, list[Security]]]:
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero.")
    return [(start, min(start + batch_size, len(securities)), securities[start:start + batch_size]) for start in range(0, len(securities), batch_size)]


def fetch_checkpoints(
    *,
    universe_path: Path,
    checkpoint_dir: Path,
    limit: int | None,
    offset: int,
    batch_size: int,
    max_batches: int | None,
    force: bool,
    price_provider: PriceProvider,
    facts_provider: CompanyFactsProvider,
    progress: bool = True,
    max_workers: int = 1,
) -> dict[str, Any]:
    securities = supported_securities(universe_path, limit=limit, offset=offset)
    batches = iter_batches(securities, batch_size)
    if max_batches is not None:
        batches = batches[:max_batches]
    benchmark = fetch_benchmark_checkpoint(price_provider, checkpoint_dir, force=force)
    summaries: list[dict[str, Any]] = []
    for batch_index, (start, end, batch) in enumerate(batches):
        payload = fetch_batch_checkpoint(
            securities=batch,
            batch_index=batch_index,
            start=start + offset,
            end=end + offset,
            checkpoint_dir=checkpoint_dir,
            price_provider=price_provider,
            facts_provider=facts_provider,
            force=force,
            progress=progress,
            max_workers=max_workers,
        )
        summaries.append({
            "path": str(checkpoint_path(checkpoint_dir, start + offset, end + offset)),
            "batchIndex": payload.get("batchIndex"),
            "startOffset": payload.get("startOffset"),
            "endOffsetExclusive": payload.get("endOffsetExclusive"),
            "attemptedTickers": payload.get("attemptedTickers"),
            "successfulTickers": payload.get("successfulTickers"),
            "failedTickers": payload.get("failedTickers"),
            "cacheHit": payload.get("cacheHit", False),
            "maxWorkers": payload.get("maxWorkers") or max_workers,
        })
        if progress:
            print(json.dumps(summaries[-1], indent=2), flush=True)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now(),
        "universePath": str(universe_path),
        "checkpointDir": str(checkpoint_dir),
        "selectedTickers": len(securities),
        "batchSize": batch_size,
        "maxWorkers": max_workers,
        "batchesRun": len(summaries),
        "benchmarkStatus": benchmark.get("status"),
        "benchmarkCacheHit": benchmark.get("cacheHit", False),
        "batches": summaries,
    }


def is_complete_batch_payload(payload: dict[str, Any]) -> bool:
    if payload.get("status") == "complete":
        return True
    if payload.get("status") == "partial":
        return False
    attempted = int(payload.get("attemptedTickers") or 0)
    processed_value = payload.get("processedTickers")
    processed = int(processed_value) if processed_value is not None else int(payload.get("successfulTickers") or 0) + int(payload.get("failedTickers") or 0)
    return attempted > 0 and processed >= attempted


class LazyCheckpointStore:
    """Read checkpointed batch files on demand so broad merges do not load all raw facts."""

    def __init__(
        self,
        *,
        checkpoint_dir: Path,
        securities: list[Security],
        batch_size: int,
        offset: int,
        cache_size: int = 1,
    ) -> None:
        self.checkpoint_dir = checkpoint_dir
        self.cache_size = max(1, cache_size)
        self._payload_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._ticker_to_path: dict[str, Path] = {}
        self._cik_to_ticker: dict[str, str] = {}
        for start, end, batch in iter_batches(securities, batch_size):
            path = checkpoint_path(checkpoint_dir, start + offset, end + offset)
            for security in batch:
                self._ticker_to_path[security.ticker] = path
                self._cik_to_ticker[security.cik.zfill(10)] = security.ticker

    def _payload(self, path: Path) -> dict[str, Any]:
        key = str(path)
        cached = self._payload_cache.get(key)
        if cached is not None:
            self._payload_cache.move_to_end(key)
            return cached
        if not path.exists():
            raise ProviderError(f"Checkpoint batch missing: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self._payload_cache[key] = payload
        while len(self._payload_cache) > self.cache_size:
            self._payload_cache.popitem(last=False)
        return payload

    def _row(self, ticker: str) -> dict[str, Any]:
        normalized_ticker = ticker.upper()
        path = self._ticker_to_path.get(normalized_ticker)
        if path is None:
            raise ProviderError(f"Ticker {normalized_ticker} is outside the checkpointed universe selection")
        payload = self._payload(path)
        if not is_complete_batch_payload(payload):
            raise ProviderError(f"Checkpoint batch is incomplete for {normalized_ticker}: {path}")
        for row in payload.get("records", []):
            security = row.get("security") or {}
            if str(security.get("ticker", "")).upper() == normalized_ticker:
                return row
        raise ProviderError(f"Checkpoint record missing for {normalized_ticker}")

    def fetch_prices(self, ticker: str) -> list[PriceBar]:
        normalized_ticker = ticker.upper()
        if normalized_ticker == BENCHMARK_TICKER:
            benchmark_path = benchmark_checkpoint_path(self.checkpoint_dir)
            benchmark = self._payload(benchmark_path)
            if benchmark.get("status") != "success":
                raise ProviderError(f"Benchmark checkpoint unavailable for {BENCHMARK_TICKER}")
            return [price_from_record(row) for row in benchmark.get("priceRows", [])]
        row = self._row(normalized_ticker)
        return [price_from_record(price) for price in row.get("priceRows", [])]

    def fetch_facts(self, cik: str) -> dict[str, Any]:
        normalized_cik = cik.zfill(10)
        ticker = self._cik_to_ticker.get(normalized_cik)
        if ticker is None:
            raise ProviderError(f"CIK {normalized_cik} is outside the checkpointed universe selection")
        return self._row(ticker).get("companyFacts") or {}

    def raw_error_summary(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in sorted(self.checkpoint_dir.glob("batch_*.status.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for ticker in payload.get("errorTickers") or []:
                summaries.append({
                    "ticker": ticker,
                    "stage": "raw_provider_fetch",
                    "message": "Ticker failed during raw checkpoint fetch; see ignored raw checkpoint logs for provider details.",
                    "batch": path.name.replace(".status.json", ".json"),
                })
        return summaries


class LazyCheckpointPriceProvider(PriceProvider):
    def __init__(self, store: LazyCheckpointStore) -> None:
        self.store = store

    def fetch(self, ticker: str) -> list[PriceBar]:
        return self.store.fetch_prices(ticker)


class LazyCheckpointCompanyFactsProvider(CompanyFactsProvider):
    def __init__(self, store: LazyCheckpointStore) -> None:
        self.store = store

    def fetch(self, cik: str) -> dict[str, Any]:
        return self.store.fetch_facts(cik)


def load_checkpointed_fixture_data(checkpoint_dir: Path, *, include_partial: bool = False) -> tuple[dict[str, list[PriceBar]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    price_records: dict[str, list[PriceBar]] = {}
    facts_records: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []

    benchmark_path = benchmark_checkpoint_path(checkpoint_dir)
    if benchmark_path.exists():
        benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
        if benchmark.get("status") == "success":
            price_records[BENCHMARK_TICKER] = [price_from_record(row) for row in benchmark.get("priceRows", [])]

    for path in batch_checkpoint_paths(checkpoint_dir):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("kind") != "raw_etl_batch_checkpoint":
            continue
        if not include_partial and not is_complete_batch_payload(payload):
            continue
        errors.extend(payload.get("errors", []))
        for row in payload.get("records", []):
            security = security_from_record(row["security"])
            price_records[security.ticker] = [price_from_record(price) for price in row.get("priceRows", [])]
            facts_records[security.cik] = row.get("companyFacts") or {}
    return price_records, facts_records, errors


def checkpoint_summary(checkpoint_dir: Path, selected_count: int, batch_size: int, *, offset: int = 0) -> dict[str, Any]:
    paths = batch_checkpoint_paths(checkpoint_dir)
    expected_ranges = [
        (start, min(start + batch_size, offset + selected_count))
        for start in range(offset, offset + selected_count, batch_size)
    ]
    expected_paths = {checkpoint_path(checkpoint_dir, start, end) for start, end in expected_ranges}
    existing_paths = set(paths)
    missing_paths = sorted(expected_paths - existing_paths)
    unexpected_paths = sorted(existing_paths - expected_paths)
    attempted = succeeded = failed = 0
    completed_batches = 0
    for path in sorted(expected_paths & existing_paths):
        status_path = checkpoint_status_path(checkpoint_dir, int(path.stem.split("_")[1]), int(path.stem.split("_")[2]))
        payload_path = status_path if status_path.exists() else path
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if payload.get("kind") != "raw_etl_batch_checkpoint":
            continue
        if not is_complete_batch_payload(payload):
            failed += int(payload.get("failedTickers") or 0)
            continue
        completed_batches += 1
        attempted += int(payload.get("attemptedTickers") or 0)
        succeeded += int(payload.get("successfulTickers") or 0)
        failed += int(payload.get("failedTickers") or 0)
    expected_batches = (selected_count + batch_size - 1) // batch_size if selected_count else 0
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now(),
        "checkpointDir": str(checkpoint_dir),
        "selectedTickers": selected_count,
        "batchSize": batch_size,
        "expectedBatches": expected_batches,
        "completedBatches": completed_batches,
        "missingBatches": len(missing_paths),
        "missingBatchPaths": [str(path) for path in missing_paths[:20]],
        "unexpectedBatchFiles": len(unexpected_paths),
        "attemptedTickersInCheckpoints": attempted,
        "successfulTickersInCheckpoints": succeeded,
        "failedTickersInCheckpoints": failed,
        "complete": not missing_paths and completed_batches >= expected_batches and attempted >= selected_count,
    }


def merge_checkpoints(
    *,
    universe_path: Path,
    checkpoint_dir: Path,
    output_dir: Path,
    limit: int | None,
    offset: int,
    batch_size: int,
    include_backtest: bool,
    allow_partial_merge: bool = False,
) -> dict[str, Any]:
    universe_records = _load_universe_records(universe_path)
    securities = supported_securities(universe_path, limit=limit, offset=offset)
    raw_summary = checkpoint_summary(checkpoint_dir, len(securities), batch_size, offset=offset)
    if not raw_summary["complete"] and not allow_partial_merge:
        raise RuntimeError(
            "Raw checkpoint set is incomplete; run --fetch-only until all batches exist "
            "or pass --allow-partial-merge for a deliberate partial publication."
        )
    store = LazyCheckpointStore(
        checkpoint_dir=checkpoint_dir,
        securities=securities,
        batch_size=batch_size,
        offset=offset,
        cache_size=1,
    )
    audit = run(
        LazyCheckpointPriceProvider(store),
        LazyCheckpointCompanyFactsProvider(store),
        output_dir,
        securities=securities,
        include_backtest=include_backtest,
        universe_records=universe_records,
    )
    audit["rawCheckpointErrors"] = store.raw_error_summary()
    audit["rawCheckpointSummary"] = raw_summary
    write_json(output_dir / "etl_report.json", audit)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Checkpointed ValueSignal ETL: fetch raw provider data in resumable batches, then merge and score globally.")
    parser.add_argument("--universe", type=Path, default=Path("data/universe/universe.json"))
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--limit", type=parse_optional_limit)
    parser.add_argument("--offset", type=parse_optional_offset, default=0)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--max-workers", type=int, default=1, help="Parallel ticker fetch workers inside each batch. Use modest values to respect provider limits.")
    parser.add_argument("--price-range", default="5y", help="Yahoo chart range to checkpoint; defaults to the normal ETL's 5-year price window.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--merge-only", action="store_true")
    parser.add_argument("--allow-partial-merge", action="store_true")
    parser.add_argument("--skip-backtest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.fetch_only and args.merge_only:
        raise SystemExit("--fetch-only and --merge-only cannot be used together.")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be greater than zero.")
    if args.max_workers < 1:
        raise SystemExit("--max-workers must be greater than zero.")

    fetch_summary: dict[str, Any] | None = None
    if not args.merge_only:
        user_agent = required_user_agent()
        fetch_summary = fetch_checkpoints(
            universe_path=args.universe,
            checkpoint_dir=args.checkpoint_dir,
            limit=args.limit,
            offset=args.offset,
            batch_size=args.batch_size,
            max_batches=args.max_batches,
            force=args.force,
            price_provider=YahooChartPriceProvider(user_agent, range_name=args.price_range),
            facts_provider=SecCompanyFactsProvider(user_agent),
            max_workers=args.max_workers,
        )
        print(json.dumps({"fetchSummary": fetch_summary}, indent=2), flush=True)

    if args.fetch_only:
        return 0

    merge_audit = merge_checkpoints(
        universe_path=args.universe,
        checkpoint_dir=args.checkpoint_dir,
        output_dir=args.output,
        limit=args.limit,
        offset=args.offset,
        batch_size=args.batch_size,
        include_backtest=not args.skip_backtest,
        allow_partial_merge=args.allow_partial_merge,
    )
    print(json.dumps({
        "fetchSummary": fetch_summary,
        "mergeAudit": {
            "status": merge_audit.get("status"),
            "requestedTickers": merge_audit.get("requestedTickers"),
            "successfulTickers": merge_audit.get("successfulTickers"),
            "failedTickers": merge_audit.get("failedTickers"),
            "runFinishedAt": merge_audit.get("runFinishedAt"),
        },
    }, indent=2), flush=True)
    return 0 if merge_audit.get("status") in {"success", "partial_success"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
