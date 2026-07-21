from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_json import write_json
from scripts.growth_spurt import (
    apply_growth_spurt_percentiles,
    calculate_growth_spurt,
    growth_spurt_counts,
    growth_spurt_mode,
    unavailable_growth_spurt_artifact,
)
from scripts.providers.price_provider import YahooChartPriceProvider


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _data_status(artifact: dict[str, Any], status: dict[str, Any] | None) -> dict[str, Any]:
    updated = dict(status or {})
    updated.update({
        "growthSpurtAvailable": artifact.get("status") != "unavailable",
        "growthSpurtStatus": artifact.get("status"),
        "growthSpurtScore": artifact.get("growthSpurtScore"),
        "growthSpurtBenchmarkPercentile": artifact.get("benchmarkPercentile"),
        "growthSpurtMarketDataAsOf": artifact.get("marketDataAsOf"),
    })
    return updated


def build_growth_spurt_artifacts(output_dir: Path, user_agent: str | None = None, mode: str | None = None) -> dict[str, Any]:
    run_at = datetime.now(timezone.utc).isoformat()
    mode = growth_spurt_mode(mode)
    dashboard_path = output_dir / "dashboard.json"
    summary_path = output_dir / "stocks" / "summary.json"
    etl_path = output_dir / "etl_report.json"
    coverage_path = output_dir / "universe_coverage_report.json"
    dashboard = _load(dashboard_path)
    summary = _load(summary_path)
    etl = _load(etl_path)
    coverage = _load(coverage_path)
    benchmark_prices: list[Any] = []
    if mode != "off":
        try:
            benchmark_prices = YahooChartPriceProvider(user_agent or "ValueSignal growth spurt artifact builder contact@example.invalid", range_name="5y").fetch("SPY")
        except Exception:
            benchmark_prices = []

    artifacts_by_ticker: dict[str, dict[str, Any]] = {}
    failures = 0
    if mode != "off":
        for path in sorted((output_dir / "stocks").glob("*.json")):
            if path.name == "summary.json":
                continue
            payload = _load(path)
            record = payload.get("record") or {}
            security = record.get("security") or {}
            ticker = str(security.get("ticker") or path.stem).upper()
            try:
                artifact = calculate_growth_spurt(ticker, record.get("priceHistory") or [], benchmark_prices, generated_at=run_at)
            except Exception as exc:
                failures += 1
                artifact = unavailable_growth_spurt_artifact(ticker, run_at, f"GROWTH_SPURT_CALCULATION_FAILED: {type(exc).__name__}: {exc}")
            artifacts_by_ticker[ticker] = artifact
        apply_growth_spurt_percentiles(list(artifacts_by_ticker.values()))

    for path in sorted((output_dir / "stocks").glob("*.json")):
        if path.name == "summary.json":
            continue
        payload = _load(path)
        record = payload.get("record") or {}
        ticker = str((record.get("security") or {}).get("ticker") or path.stem).upper()
        artifact = artifacts_by_ticker.get(ticker)
        if artifact:
            record["growthSpurt"] = artifact
            record["dataStatus"] = _data_status(artifact, record.get("dataStatus"))
            write_json(path, payload)

    for row in dashboard.get("records") or []:
        ticker = str((row.get("security") or {}).get("ticker") or "").upper()
        artifact = artifacts_by_ticker.get(ticker)
        if artifact:
            row["growthSpurt"] = artifact
            row["dataStatus"] = _data_status(artifact, row.get("dataStatus"))
    for row in summary.get("records") or []:
        ticker = str(row.get("ticker") or "").upper()
        artifact = artifacts_by_ticker.get(ticker)
        if artifact:
            row["growthSpurt"] = artifact
            row["dataStatus"] = _data_status(artifact, row.get("dataStatus"))

    counts = growth_spurt_counts(artifacts_by_ticker.values(), failures, mode)
    etl["growthSpurtCoverage"] = counts
    etl.setdefault("coverageCounts", {}).update(counts)
    coverage.setdefault("counts", {}).update(counts)
    write_json(dashboard_path, dashboard)
    write_json(summary_path, summary)
    write_json(etl_path, etl)
    write_json(coverage_path, coverage)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate Growth Spurt artifacts from generated stock price histories.")
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--mode", default=None)
    args = parser.parse_args()
    contact = os.getenv("VS_USER_AGENT") or os.getenv("VS_CONTACT_EMAIL") or "ValueSignal growth spurt artifact builder contact@example.invalid"
    counts = build_growth_spurt_artifacts(args.output, contact, args.mode)
    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
