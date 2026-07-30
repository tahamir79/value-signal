from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.export_json import write_json
from scripts.features import FEATURE_SCHEMA_VERSION, normalize_universe
from scripts.growth_spurt import apply_growth_spurt_percentiles, growth_spurt_counts
from scripts.providers.price_provider import YahooChartPriceProvider
from scripts.providers.sec_companyfacts import SecCompanyFactsProvider
from scripts.run_etl import _load_universe_records, run as run_etl
from scripts.scoring import SCORE_SCHEMA_VERSION, score_universe

STATE_SCHEMA_VERSION = "1.0.0"
DEFAULT_PUBLIC_DATA = Path("public/data")
DEFAULT_STATE_PATH = Path("data/reports/scheduled_etl_batch_state.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback or {})


def ticker_from_dashboard_row(row: dict[str, Any]) -> str:
    return str((row.get("security") or {}).get("ticker") or row.get("ticker") or "").upper()


def supported_universe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("isSupported", True) and row.get("ticker") and row.get("cik")]


def universe_fingerprint(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in supported_universe_rows(rows):
        digest.update(str(row.get("ticker", "")).upper().encode("utf-8"))
        digest.update(b"|")
        digest.update(str(row.get("cik", "")).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def select_refresh_rows(
    rows: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    batch_size: int,
    batch_count: int,
    daily_sweep_slots: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    supported = supported_universe_rows(rows)
    if not supported:
        raise ValueError("Universe has no supported rows to refresh.")
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero.")
    if batch_count < 1:
        raise ValueError("batch_count must be greater than zero.")
    if daily_sweep_slots < 1:
        raise ValueError("daily_sweep_slots must be greater than zero.")

    fingerprint = universe_fingerprint(rows)
    next_offset = int(state.get("nextOffset") or 0)
    if state.get("universeFingerprint") not in {None, fingerprint}:
        next_offset = 0

    total = len(supported)
    requested = min(total, batch_size * batch_count)
    start_offset = next_offset % total
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = start_offset
    while len(selected) < requested:
        row = supported[cursor % total]
        ticker = str(row["ticker"]).upper()
        if ticker not in seen:
            selected.append(row)
            seen.add(ticker)
        cursor += 1
        if cursor - start_offset >= total:
            break

    next_state = {
        "schemaVersion": STATE_SCHEMA_VERSION,
        "universeFingerprint": fingerprint,
        "universeSize": total,
        "previousOffset": start_offset,
        "nextOffset": cursor % total,
        "batchSize": batch_size,
        "batchCount": batch_count,
        "dailySweepSlots": daily_sweep_slots,
        "plannedDailyRefreshTickers": min(total, batch_size * batch_count * daily_sweep_slots),
        "selectedTickers": [str(row["ticker"]).upper() for row in selected],
        "updatedAt": utc_now(),
    }
    return selected, next_state


def security_from_row(row: dict[str, Any]):
    from scripts.models import Security

    return Security(
        str(row["ticker"]).upper(),
        str(row["cik"]).zfill(10),
        str(row.get("companyName") or row.get("name") or row["ticker"]),
        str(row.get("exchange") or "UNKNOWN"),
        str(row.get("sector") or "Unknown"),
    )


def feature_seed(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row["ticker"],
        "asOf": row.get("asOf"),
        "raw": dict(row.get("raw") or {}),
        "balanceSheetScoring": row.get("balanceSheetScoring"),
    }


def apply_signal_status(status: dict[str, Any] | None, signal: dict[str, Any] | None) -> dict[str, Any]:
    updated = dict(status or {})
    if not signal:
        return updated
    updated.update({
        "scoringInputsAvailable": int(signal.get("availableFeatures") or 0) >= 5,
        "scoringAvailable": signal.get("confidence") != "Insufficient",
        "officialSignal": signal.get("signal"),
        "latestScoringDate": signal.get("asOf"),
        "insufficientEvidenceReason": "Insufficient scoring inputs" if signal.get("confidence") == "Insufficient" else None,
    })
    return updated


def apply_growth_status(status: dict[str, Any] | None, artifact: dict[str, Any] | None) -> dict[str, Any]:
    updated = dict(status or {})
    if not artifact:
        return updated
    updated.update({
        "growthSpurtAvailable": artifact.get("status") != "unavailable",
        "growthSpurtStatus": artifact.get("status"),
        "growthSpurtScore": artifact.get("growthSpurtScore"),
        "growthSpurtBenchmarkPercentile": artifact.get("benchmarkPercentile"),
        "growthSpurtMarketDataAsOf": artifact.get("marketDataAsOf"),
    })
    return updated


def merge_dashboard_records(existing: list[dict[str, Any]], refreshed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ticker = {ticker_from_dashboard_row(row): row for row in existing if ticker_from_dashboard_row(row)}
    order = [ticker_from_dashboard_row(row) for row in existing if ticker_from_dashboard_row(row)]
    for row in refreshed:
        ticker = ticker_from_dashboard_row(row)
        if not ticker:
            continue
        if ticker not in by_ticker:
            order.append(ticker)
        by_ticker[ticker] = row
    return [by_ticker[ticker] for ticker in order if ticker in by_ticker]


def write_summary(public_data: Path, dashboard_records: list[dict[str, Any]], generated_at: str) -> None:
    summary = {
        "schemaVersion": "1.0.0",
        "generatedAt": generated_at,
        "records": [
            {
                "ticker": row["security"]["ticker"],
                "companyName": row["security"]["company_name"],
                "exchange": row["security"]["exchange"],
                "sector": row["security"].get("sector"),
                "derived": row.get("derived") or {},
                "dataStatus": row.get("dataStatus") or {},
                "growthSpurt": row.get("growthSpurt"),
            }
            for row in dashboard_records
        ],
    }
    write_json(public_data / "stocks" / "summary.json", summary)


def update_coverage_counts(
    coverage: dict[str, Any],
    *,
    dashboard_records: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    growth_counts: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    signal_rows = signals
    scoreable = [row for row in signal_rows if row.get("confidence") != "Insufficient"]
    insufficient = [
        row for row in signal_rows
        if row.get("confidence") == "Insufficient" or row.get("signal") == "insufficient-evidence"
    ]
    statuses = [row.get("dataStatus") or {} for row in dashboard_records]
    counts = dict((coverage.get("counts") or {}))
    counts.update({
        "scoreable_companies": len(scoreable),
        "insufficient_evidence_companies": len(insufficient),
        "companyfacts_available": sum(1 for status in statuses if status.get("companyFactsAvailable")),
        "balance_sheets_available": sum(1 for status in statuses if status.get("balanceSheetAvailable")),
        "balance_sheets_partial": sum(1 for status in statuses if status.get("balanceSheetPartial")),
        "balance_sheets_unavailable": sum(1 for status in statuses if not status.get("balanceSheetAvailable") and not status.get("balanceSheetPartial")),
    })
    counts.update(growth_counts)
    coverage["generatedAt"] = generated_at
    coverage["counts"] = counts
    coverage["insufficientEvidence"] = [
        {
            "ticker": row["ticker"],
            "reason": "Insufficient scoring inputs",
        }
        for row in insufficient
    ]
    return coverage


def merge_refreshed_batch(
    *,
    public_data: Path,
    batch_output: Path,
    state: dict[str, Any],
    batch_audit: dict[str, Any],
) -> dict[str, Any]:
    generated_at = utc_now()
    dashboard = load_json(public_data / "dashboard.json", {"records": [], "schemaVersion": "1.0.0", "mode": "live"})
    batch_dashboard = load_json(batch_output / "dashboard.json", {"records": []})
    features = load_json(public_data / "features.json", {"records": []})
    batch_features = load_json(batch_output / "features.json", {"records": []})
    coverage = load_json(public_data / "universe_coverage_report.json", {"counts": {}})

    dashboard_records = merge_dashboard_records(dashboard.get("records") or [], batch_dashboard.get("records") or [])
    feature_by_ticker = {str(row.get("ticker") or "").upper(): row for row in features.get("records") or []}
    for row in batch_features.get("records") or []:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            feature_by_ticker[ticker] = row

    ordered_tickers = [ticker_from_dashboard_row(row) for row in dashboard_records if ticker_from_dashboard_row(row)]
    feature_rows = [feature_seed(feature_by_ticker[ticker]) for ticker in ordered_tickers if ticker in feature_by_ticker]
    normalized_features = normalize_universe(feature_rows)
    signal_records = score_universe(normalized_features)
    signal_by_ticker = {str(row.get("ticker") or "").upper(): row for row in signal_records}

    for row in dashboard_records:
        ticker = ticker_from_dashboard_row(row)
        row["dataStatus"] = apply_signal_status(row.get("dataStatus"), signal_by_ticker.get(ticker))

    growth_artifacts = [row.get("growthSpurt") for row in dashboard_records if isinstance(row.get("growthSpurt"), dict)]
    apply_growth_spurt_percentiles(growth_artifacts)
    growth_by_ticker = {str(artifact.get("ticker") or "").upper(): artifact for artifact in growth_artifacts}
    for row in dashboard_records:
        ticker = ticker_from_dashboard_row(row)
        artifact = growth_by_ticker.get(ticker)
        if artifact:
            row["growthSpurt"] = artifact
            row["dataStatus"] = apply_growth_status(row.get("dataStatus"), artifact)

    public_stock_dir = public_data / "stocks"
    public_stock_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted((batch_output / "stocks").glob("*.json")):
        if source.name == "summary.json":
            continue
        shutil.copy2(source, public_stock_dir / source.name)

    dashboard.update({"schemaVersion": "1.0.0", "generatedAt": generated_at, "mode": "live", "records": dashboard_records})
    merged_features = {
        "schemaVersion": FEATURE_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "universeSize": len(normalized_features),
        "records": normalized_features,
    }
    merged_signals = {
        "schemaVersion": SCORE_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "universeSize": len(signal_records),
        "records": signal_records,
    }
    growth_counts = growth_spurt_counts(growth_artifacts, 0, os.getenv("GROWTH_SPURT_MODE", "display"))
    coverage = update_coverage_counts(
        coverage,
        dashboard_records=dashboard_records,
        signals=signal_records,
        growth_counts=growth_counts,
        generated_at=generated_at,
    )

    merged_audit = {
        **load_json(public_data / "etl_report.json", {}),
        "schemaVersion": "1.0.0",
        "runStartedAt": batch_audit.get("runStartedAt"),
        "runFinishedAt": generated_at,
        "status": "success" if not batch_audit.get("failedTickers") else "partial_success",
        "requestedTickers": batch_audit.get("requestedTickers", len(state.get("selectedTickers") or [])),
        "successfulTickers": batch_audit.get("successfulTickers", 0),
        "failedTickers": batch_audit.get("failedTickers", 0),
        "errors": batch_audit.get("errors") or [],
        "tickers": batch_audit.get("tickers") or [],
        "coverageCounts": coverage.get("counts") or {},
        "growthSpurtCoverage": growth_counts,
        "publicationMode": "incremental_batch_merge",
        "fullUniversePublishedTickers": len(dashboard_records),
        "batchState": state,
    }

    write_json(public_data / "dashboard.json", dashboard)
    write_json(public_data / "features.json", merged_features)
    write_json(public_data / "signals.json", merged_signals)
    write_json(public_data / "universe_coverage_report.json", coverage)
    write_json(public_data / "etl_report.json", merged_audit)
    write_summary(public_data, dashboard_records, generated_at)
    return merged_audit


def run_batch_refresh(args: argparse.Namespace) -> dict[str, Any]:
    universe_records = _load_universe_records(args.universe)
    state = load_json(args.state_path, {})
    daily_sweep_slots = int(os.getenv("VS_DAILY_SWEEP_SLOTS") or "1")
    selected_rows, next_state = select_refresh_rows(
        universe_records,
        state,
        batch_size=args.batch_size,
        batch_count=args.batch_count,
        daily_sweep_slots=daily_sweep_slots,
    )
    if args.dry_run:
        return {
            "status": "dry_run",
            "selectedTickers": next_state["selectedTickers"],
            "previousOffset": next_state["previousOffset"],
            "nextOffset": next_state["nextOffset"],
            "universeSize": next_state["universeSize"],
            "dailySweepSlots": next_state["dailySweepSlots"],
            "plannedDailyRefreshTickers": next_state["plannedDailyRefreshTickers"],
        }

    user_agent = os.getenv("VS_USER_AGENT", "")
    if not user_agent or "@" not in user_agent:
        raise RuntimeError("VS_USER_AGENT must identify the application and include a contact email.")

    securities = [security_from_row(row) for row in selected_rows]
    work_dir = args.work_dir
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(work_dir)) as temp_name:
        batch_output = Path(temp_name) / "public_data"
        batch_audit = run_etl(
            YahooChartPriceProvider(user_agent, range_name="5y"),
            SecCompanyFactsProvider(user_agent),
            batch_output,
            securities=securities,
            include_backtest=not args.skip_backtest,
            universe_records=selected_rows,
        )
        if not batch_audit.get("successfulTickers"):
            raise RuntimeError("Scheduled batch refresh produced zero successful tickers; public artifacts were not changed.")
        next_state.update({
            "lastRunStartedAt": batch_audit.get("runStartedAt"),
            "lastRunFinishedAt": batch_audit.get("runFinishedAt"),
            "lastSuccessfulTickers": batch_audit.get("successfulTickers"),
            "lastFailedTickers": batch_audit.get("failedTickers"),
        })
        merged_audit = merge_refreshed_batch(
            public_data=args.public_data,
            batch_output=batch_output,
            state=next_state,
            batch_audit=batch_audit,
        )
    write_json(args.state_path, next_state)
    return {
        "status": merged_audit["status"],
        "publicationMode": merged_audit["publicationMode"],
        "selectedTickers": next_state["selectedTickers"],
        "successfulTickers": merged_audit["successfulTickers"],
        "failedTickers": merged_audit["failedTickers"],
        "fullUniversePublishedTickers": merged_audit["fullUniversePublishedTickers"],
        "nextOffset": next_state["nextOffset"],
        "dailySweepSlots": next_state["dailySweepSlots"],
        "plannedDailyRefreshTickers": next_state["plannedDailyRefreshTickers"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh a safe live ETL batch and merge it into the published full-universe artifacts.")
    parser.add_argument("--universe", type=Path, default=Path("data/universe/universe.json"))
    parser.add_argument("--public-data", type=Path, default=DEFAULT_PUBLIC_DATA)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--work-dir", type=Path, default=Path(".tmp/scheduled_etl_batch"))
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("--batch-count", type=int, default=1)
    parser.add_argument("--skip-backtest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    try:
        result = run_batch_refresh(parse_args())
    except Exception as exc:
        print(f"Scheduled batch refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
