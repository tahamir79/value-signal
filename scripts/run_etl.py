from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_universe import build_universe
from scripts.backtest import build_point_in_time_snapshots, empty_report, evaluate_snapshots
from scripts.cleaning import latest_facts, normalize_company_facts
from scripts.export_json import write_json
from scripts.features import FEATURE_SCHEMA_VERSION, calculate_raw_features, derive_fields, normalize_universe
from scripts.models import record
from scripts.providers.price_provider import PriceProvider, YahooChartPriceProvider
from scripts.providers.sec_companyfacts import CompanyFactsProvider, SecCompanyFactsProvider
from scripts.scoring import SCORE_SCHEMA_VERSION, score_universe

SCHEMA_VERSION = "1.0.0"

def run(price_provider: PriceProvider, facts_provider: CompanyFactsProvider, output_dir: Path, limit: int | None = None) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    price_history: dict[str, list[Any]] = {}
    fact_history: dict[str, list[Any]] = {}
    errors: list[dict[str, str]] = []
    ticker_reports: list[dict[str, Any]] = []
    for security in build_universe(limit):
        began = perf_counter()
        report: dict[str, Any] = {"ticker": security.ticker, "status": "success", "priceRows": 0, "financialFacts": 0}
        try:
            prices = price_provider.fetch(security.ticker)
            facts = normalize_company_facts(facts_provider.fetch(security.cik))
            price_history[security.ticker] = prices
            fact_history[security.ticker] = facts
            latest = latest_facts(facts)
            report.update(priceRows=len(prices), financialFacts=len(facts))
            rows.append({"security": record(security), "derived": derive_fields(prices, latest), "latestFacts": {name: record(fact) for name, fact in latest.items()}, "priceHistory": [record(bar) for bar in prices[-260:]]})
            feature_rows.append({"ticker": security.ticker, "asOf": prices[-1].date, "raw": calculate_raw_features(prices, facts)})
        except Exception as exc:  # ticker boundary: never abort the universe
            report["status"] = "failed"
            report["error"] = f"{type(exc).__name__}: {exc}"
            errors.append({"ticker": security.ticker, "stage": "ticker_pipeline", "message": report["error"]})
        finally:
            report["durationMs"] = round((perf_counter() - began) * 1000)
            ticker_reports.append(report)
    finished = datetime.now(timezone.utc)
    dashboard = {"schemaVersion": SCHEMA_VERSION, "generatedAt": finished.isoformat(), "mode": "live", "records": rows}
    normalized_features = normalize_universe(feature_rows)
    features = {"schemaVersion": FEATURE_SCHEMA_VERSION, "generatedAt": finished.isoformat(), "universeSize": len(feature_rows), "records": normalized_features}
    signals = {"schemaVersion": SCORE_SCHEMA_VERSION, "generatedAt": finished.isoformat(), "universeSize": len(feature_rows), "records": score_universe(normalized_features)}
    try:
        benchmark_prices = price_provider.fetch("SPY")
        eligible_dates = [bar.date for index, bar in enumerate(benchmark_prices) if index >= 252 and index + 90 < len(benchmark_prices)]
        signal_dates = eligible_dates[::21]
        snapshots = build_point_in_time_snapshots(price_history, fact_history, signal_dates)
        backtest = evaluate_snapshots(snapshots, price_history, benchmark_prices, [report["ticker"] for report in ticker_reports])
    except Exception as exc:
        backtest = empty_report(f"Backtest generation unavailable: {type(exc).__name__}: {exc}", finished.isoformat())
    audit = {"schemaVersion": SCHEMA_VERSION, "runStartedAt": started.isoformat(), "runFinishedAt": finished.isoformat(), "status": "success" if not errors else "partial_success", "requestedTickers": len(ticker_reports), "successfulTickers": len(rows), "failedTickers": len(errors), "errors": errors, "tickers": ticker_reports}
    write_json(output_dir / "dashboard.json", dashboard)
    write_json(output_dir / "features.json", features)
    write_json(output_dir / "signals.json", signals)
    write_json(output_dir / "backtest_results.json", backtest)
    write_json(output_dir / "etl_report.json", audit)
    return audit

def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ValueSignal market and SEC ETL pipeline")
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    user_agent = os.getenv("VS_USER_AGENT", "")
    if not user_agent or "@" not in user_agent:
        print("VS_USER_AGENT must identify the application and include a contact email.", file=sys.stderr)
        return 2
    audit = run(YahooChartPriceProvider(user_agent, range_name="5y"), SecCompanyFactsProvider(user_agent), args.output, args.limit)
    print(f"ETL {audit['status']}: {audit['successfulTickers']}/{audit['requestedTickers']} tickers published")
    return 0 if audit["successfulTickers"] else 1

if __name__ == "__main__": raise SystemExit(main())
