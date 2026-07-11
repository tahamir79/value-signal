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
from scripts.models import Security
from scripts.providers.price_provider import PriceProvider, YahooChartPriceProvider
from scripts.providers.sec_companyfacts import CompanyFactsProvider, SecCompanyFactsProvider
from scripts.scoring import SCORE_SCHEMA_VERSION, score_universe

SCHEMA_VERSION = "1.0.0"

def _securities_from_universe_file(path: Path, limit: int | None = None) -> list[Security]:
    import json
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("records") or payload
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
    return securities


def run(price_provider: PriceProvider, facts_provider: CompanyFactsProvider, output_dir: Path,
        limit: int | None = None, securities: list[Security] | None = None,
        include_backtest: bool = True) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    price_history: dict[str, list[Any]] = {}
    fact_history: dict[str, list[Any]] = {}
    errors: list[dict[str, str]] = []
    ticker_reports: list[dict[str, Any]] = []
    universe = securities if securities is not None else build_universe(limit)
    for security in universe:
        began = perf_counter()
        report: dict[str, Any] = {"ticker": security.ticker, "status": "success", "priceRows": 0, "financialFacts": 0}
        try:
            prices = price_provider.fetch(security.ticker)
            facts = normalize_company_facts(facts_provider.fetch(security.cik))
            price_history[security.ticker] = prices
            fact_history[security.ticker] = facts
            latest = latest_facts(facts)
            report.update(priceRows=len(prices), financialFacts=len(facts))
            detail_row = {"security": record(security), "derived": derive_fields(prices, latest), "latestFacts": {name: record(fact) for name, fact in latest.items()}, "priceHistory": [record(bar) for bar in prices[-260:]]}
            write_json(output_dir / "stocks" / f"{security.ticker}.json", {"schemaVersion": SCHEMA_VERSION, "generatedAt": datetime.now(timezone.utc).isoformat(), "record": detail_row})
            rows.append({"security": record(security), "derived": detail_row["derived"]})
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
        if not include_backtest:
            raise RuntimeError("Backtest skipped for scaled ETL artifact size control")
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
    parser.add_argument("--universe", type=Path, help="Optional scaled universe JSON from scripts/universe/build_universe.py")
    parser.add_argument("--skip-backtest", action="store_true", help="Write a small unavailable backtest report for scaled runs")
    args = parser.parse_args()
    user_agent = os.getenv("VS_USER_AGENT", "")
    if not user_agent or "@" not in user_agent:
        print("VS_USER_AGENT must identify the application and include a contact email.", file=sys.stderr)
        return 2
    securities = _securities_from_universe_file(args.universe, args.limit) if args.universe else None
    audit = run(YahooChartPriceProvider(user_agent, range_name="5y"), SecCompanyFactsProvider(user_agent), args.output, args.limit, securities, include_backtest=not args.skip_backtest)
    print(f"ETL {audit['status']}: {audit['successfulTickers']}/{audit['requestedTickers']} tickers published")
    return 0 if audit["successfulTickers"] else 1

if __name__ == "__main__": raise SystemExit(main())
