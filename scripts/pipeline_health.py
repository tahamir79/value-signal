from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_json import write_json

REPORT_SCHEMA_VERSION = "1.0.0"
PUBLIC_DATA = Path("public/data")
REPORT_DIR = Path("data/reports")

CORE_ARTIFACTS = [
    PUBLIC_DATA / "dashboard.json",
    PUBLIC_DATA / "features.json",
    PUBLIC_DATA / "signals.json",
    PUBLIC_DATA / "etl_report.json",
    PUBLIC_DATA / "universe_coverage_report.json",
    PUBLIC_DATA / "stocks" / "summary.json",
    PUBLIC_DATA / "forecasts" / "summary.json",
    PUBLIC_DATA / "search_index.json",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def normalize_failure(message: str) -> tuple[str, bool]:
    text = message or ""
    if "HTTP Error 404" in text:
        return "PROVIDER_HTTP_404", False
    if re.search(r"HTTP Error (429|500|502|503|504)", text):
        return "PROVIDER_RETRYABLE_HTTP_ERROR", True
    if "companyfacts" in text.lower():
        return "SEC_COMPANYFACTS_UNAVAILABLE", True
    if "price" in text.lower() or "chart" in text.lower():
        return "PRICE_HISTORY_UNAVAILABLE", True
    if "cik" in text.lower():
        return "TICKER_CIK_MAPPING_MISSING", False
    return "PROVIDER_REQUEST_FAILED", True


def _stage(
    *,
    name: str,
    status: str,
    attempted: int = 0,
    succeeded: int = 0,
    failed: int = 0,
    skipped: int = 0,
    failed_tickers: list[str] | None = None,
    reasons: Counter[str] | None = None,
    artifact_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "failedTickers": failed_tickers or [],
        "commonReasons": [{"reason": reason, "count": count} for reason, count in (reasons or Counter()).most_common()],
        "artifactPaths": artifact_paths or [],
    }


def _core_artifact_stage() -> tuple[dict[str, Any], int]:
    missing = [str(path.as_posix()) for path in CORE_ARTIFACTS if not path.exists()]
    return _stage(
        name="core_artifacts",
        status="failed" if missing else "success",
        attempted=len(CORE_ARTIFACTS),
        succeeded=len(CORE_ARTIFACTS) - len(missing),
        failed=len(missing),
        artifact_paths=[str(path.as_posix()) for path in CORE_ARTIFACTS if path.exists()],
        reasons=Counter({"CRITICAL_ARTIFACT_MISSING": len(missing)}) if missing else Counter(),
    ), len(missing)


def _etl_stage(etl: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    errors = etl.get("errors") if isinstance(etl.get("errors"), list) else []
    failed_tickers = []
    reasons: Counter[str] = Counter()
    failures = []
    for error in errors:
        ticker = str(error.get("ticker") or "UNKNOWN")
        reason, retryable = normalize_failure(str(error.get("message") or ""))
        failed_tickers.append(ticker)
        reasons[reason] += 1
        failures.append({"ticker": ticker, "stage": error.get("stage") or "ticker_pipeline", "reason": reason, "retryable": retryable})
    attempted = int(etl.get("requestedTickers") or 0)
    succeeded = int(etl.get("successfulTickers") or 0)
    failed = int(etl.get("failedTickers") or len(failures))
    status = "success" if attempted and not failed else "partial_success" if attempted and succeeded else "failed"
    return _stage(
        name="etl_ticker_pipeline",
        status=status,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        failed_tickers=failed_tickers,
        reasons=reasons,
        artifact_paths=["public/data/etl_report.json", "public/data/dashboard.json", "public/data/stocks"],
    ), failures


def _backtest_stage(backtest: dict[str, Any]) -> dict[str, Any]:
    notes = " ".join(str(note) for note in (backtest.get("biasAudit") or {}).get("notes", []))
    expected_skip = "Backtest skipped for scaled ETL artifact size control" in notes
    status = "unavailable_expected" if expected_skip else "success" if backtest.get("status") == "complete" else "partial_success"
    return _stage(
        name="backtest",
        status=status,
        attempted=int(backtest.get("snapshotCount") or 0),
        succeeded=int(backtest.get("evaluatedObservationCount") or 0),
        skipped=1 if expected_skip else 0,
        reasons=Counter({"EXPECTED_BACKTEST_SKIPPED": 1}) if expected_skip else Counter(),
        artifact_paths=["public/data/backtest_results.json"],
    )


def _forecast_stage(summary: dict[str, Any]) -> dict[str, Any]:
    count = int(summary.get("count") or 0)
    sources = summary.get("displayProjectionSources") or {}
    unavailable = int(sources.get("unavailable") or 0)
    status = "failed" if not count else "success"
    reasons = Counter()
    scenario_status = summary.get("conservativeScenarioStatus") or {}
    if scenario_status.get("insufficient_data"):
        reasons["FORECAST_INSUFFICIENT_HISTORY"] = int(scenario_status["insufficient_data"])
    if unavailable:
        reasons["PROJECTION_SOURCE_UNAVAILABLE"] = unavailable
    return _stage(
        name="forecast_artifacts",
        status=status,
        attempted=count,
        succeeded=max(0, count - unavailable),
        failed=0,
        skipped=unavailable,
        reasons=reasons,
        artifact_paths=["public/data/forecasts/summary.json", "public/data/forecasts", "models/forecast"],
    )


def _search_stage(index: dict[str, Any]) -> dict[str, Any]:
    docs = int(index.get("documentCount") or 0)
    tickers = int(index.get("tickerCount") or 0)
    return _stage(
        name="filing_search_index",
        status="success" if docs and tickers else "failed",
        attempted=tickers,
        succeeded=tickers,
        failed=0 if docs and tickers else 1,
        reasons=Counter({"SEARCH_INDEX_EMPTY": 1}) if not docs else Counter(),
        artifact_paths=["public/data/search_index.json", "public/data/search"],
    )


def _balance_sheet_stage(coverage: dict[str, Any]) -> dict[str, Any]:
    counts = coverage.get("counts") or {}
    available = int(counts.get("balance_sheets_available") or 0)
    partial = int(counts.get("balance_sheets_partial") or 0)
    unavailable = int(counts.get("balance_sheets_unavailable") or 0)
    attempted = available + partial + unavailable
    if not attempted:
        attempted = int(counts.get("successfulTickers") or counts.get("companyfacts_available") or counts.get("scoreable_companies") or 0)
    reasons = Counter()
    if partial:
        reasons["BALANCE_SHEET_PARTIAL"] = partial
    if unavailable:
        reasons["BALANCE_SHEET_UNAVAILABLE"] = unavailable
    return _stage(
        name="balance_sheet_context",
        status="partial_success" if partial or unavailable else "success",
        attempted=attempted,
        succeeded=available + partial,
        failed=0,
        skipped=unavailable,
        reasons=reasons,
        artifact_paths=["public/data/universe_coverage_report.json", "data/fundamentals/balance_sheets"],
    )


def _growth_spurt_stage(etl: dict[str, Any]) -> dict[str, Any]:
    coverage = etl.get("growthSpurtCoverage") or etl.get("coverageCounts") or {}
    mode = str(coverage.get("growthSpurtMode") or "display")
    attempted = int(coverage.get("stocksGrowthSpurtAttempted") or 0)
    detected = int(coverage.get("stocksGrowthSpurtDetected") or 0)
    emerging = int(coverage.get("stocksGrowthSpurtEmerging") or 0)
    not_detected = int(coverage.get("stocksGrowthSpurtNotDetected") or 0)
    unavailable = int(coverage.get("stocksGrowthSpurtUnavailable") or 0)
    failures = int(coverage.get("growthSpurtCalculationFailures") or 0)
    reasons = Counter()
    if unavailable:
        reasons["GROWTH_SPURT_UNAVAILABLE_EXPECTED"] = unavailable
    if failures:
        reasons["GROWTH_SPURT_CALCULATION_FAILURE"] = failures
    if mode == "off":
        return _stage(
            name="growth_spurt_detector",
            status="unavailable_expected",
            attempted=0,
            skipped=1,
            reasons=Counter({"GROWTH_SPURT_MODE_OFF": 1}),
            artifact_paths=["public/data/stocks", "public/data/etl_report.json"],
        )
    status = "failed" if not attempted else "partial_success" if failures else "success"
    return _stage(
        name="growth_spurt_detector",
        status=status,
        attempted=attempted,
        succeeded=detected + emerging + not_detected,
        failed=failures,
        skipped=unavailable,
        reasons=reasons,
        artifact_paths=["public/data/stocks", "public/data/etl_report.json", "data/reports/growth_spurt_benchmark.json"],
    )


def _analyst_targets_stage(forecast: dict[str, Any]) -> dict[str, Any]:
    count = int(forecast.get("count") or 0)
    return _stage(
        name="market_targets",
        status="unavailable_expected",
        attempted=count,
        succeeded=0,
        skipped=count,
        reasons=Counter({"ANALYST_TARGET_PROVIDER_NOT_CONFIGURED": count}) if count else Counter({"ANALYST_TARGET_PROVIDER_NOT_CONFIGURED": 1}),
        artifact_paths=["public/data/forecasts/summary.json"],
    )


def build_health_report() -> dict[str, Any]:
    etl = _load(PUBLIC_DATA / "etl_report.json")
    coverage = _load(PUBLIC_DATA / "universe_coverage_report.json")
    forecast = _load(PUBLIC_DATA / "forecasts" / "summary.json")
    backtest = _load(PUBLIC_DATA / "backtest_results.json")
    search = _load(PUBLIC_DATA / "search_index.json")
    core_stage, critical_failures = _core_artifact_stage()
    etl_stage, failed_tickers = _etl_stage(etl)
    stages = [
        core_stage,
        etl_stage,
        _backtest_stage(backtest),
        _forecast_stage(forecast),
        _search_stage(search),
        _balance_sheet_stage(coverage),
        _growth_spurt_stage(etl),
        _analyst_targets_stage(forecast),
    ]
    noncritical_failures = sum(stage["failed"] for stage in stages if stage["name"] != "core_artifacts")
    expected_unavailable = sum(stage["skipped"] for stage in stages if stage["status"] == "unavailable_expected")
    data_quality_warnings = sum(
        sum(reason["count"] for reason in stage["commonReasons"])
        for stage in stages
        if stage["status"] == "partial_success" and stage["failed"] == 0
    )
    warnings = data_quality_warnings + sum(
        sum(reason["count"] for reason in stage["commonReasons"])
        for stage in stages
        if stage["status"] == "failed"
    )
    if critical_failures:
        overall = "failed"
    elif any(stage["status"] == "failed" for stage in stages):
        overall = "failed"
    elif etl_stage["failed"]:
        overall = "partial_success"
    else:
        overall = "success"
    release_readiness = "blocked" if overall == "failed" else "ready_with_known_limitations" if overall == "partial_success" else "ready"
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "generatedAt": _now(),
        "overallStatus": overall,
        "releaseReadiness": release_readiness,
        "criticalFailures": critical_failures,
        "nonCriticalFailures": noncritical_failures,
        "expectedUnavailable": expected_unavailable,
        "dataQualityWarnings": data_quality_warnings,
        "warnings": warnings,
        "stages": stages,
        "failedTickers": failed_tickers,
    }


def public_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": report["schemaVersion"],
        "generatedAt": report["generatedAt"],
        "overallStatus": report["overallStatus"],
        "releaseReadiness": report["releaseReadiness"],
        "criticalFailures": report["criticalFailures"],
        "nonCriticalFailures": report["nonCriticalFailures"],
        "expectedUnavailable": report["expectedUnavailable"],
        "dataQualityWarnings": report["dataQualityWarnings"],
        "warnings": report["warnings"],
        "stages": [
            {
                "name": stage["name"],
                "status": stage["status"],
                "attempted": stage["attempted"],
                "succeeded": stage["succeeded"],
                "failed": stage["failed"],
                "skipped": stage["skipped"],
                "commonReasons": stage["commonReasons"],
            }
            for stage in report["stages"]
        ],
        "failedTickers": report["failedTickers"],
    }


def main() -> int:
    report = build_health_report()
    write_json(REPORT_DIR / "pipeline_health_report.json", report)
    write_json(PUBLIC_DATA / "pipeline_health.json", public_summary(report))
    print(json.dumps({"status": report["overallStatus"], "criticalFailures": report["criticalFailures"], "nonCriticalFailures": report["nonCriticalFailures"]}, indent=2))
    return 0 if report["overallStatus"] != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
