from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backtest import build_point_in_time_snapshots, empty_report, evaluate_snapshots
from scripts.balance_sheet import balance_sheet_bundle, experimental_signal, write_balance_sheet_artifacts
from scripts.build_universe import build_universe
from scripts.cleaning import latest_facts, normalize_company_facts
from scripts.export_json import write_json
from scripts.features import FEATURE_SCHEMA_VERSION, calculate_raw_features, derive_fields, normalize_universe
from scripts.models import Security, record
from scripts.providers.price_provider import PriceProvider, YahooChartPriceProvider
from scripts.providers.sec_companyfacts import CompanyFactsProvider, SecCompanyFactsProvider
from scripts.scoring import SCORE_SCHEMA_VERSION, balance_sheet_scoring_mode, score_universe

SCHEMA_VERSION = "1.0.0"
PRICE_HISTORY_EXPORT_SESSIONS = 1260


def remove_stale_stock_artifacts(output_dir: Path, active_tickers: set[str]) -> list[str]:
    """Delete generated stock detail artifacts that are no longer in the active ETL output."""
    stock_dir = output_dir / "stocks"
    if not stock_dir.exists():
        return []
    active = {ticker.upper() for ticker in active_tickers}
    removed: list[str] = []
    for path in stock_dir.glob("*.json"):
        if path.name == "summary.json":
            continue
        ticker = path.stem.upper()
        if ticker not in active:
            path.unlink()
            removed.append(ticker)
    return sorted(removed)


def _empty_status(run_at: str) -> dict[str, Any]:
    return {
        "rawSecTraceable": True,
        "submissionsAvailable": False,
        "companyFactsAvailable": False,
        "recent10KAvailable": False,
        "recent10QAvailable": False,
        "filingsDownloaded": False,
        "filingsCleaned": False,
        "filingsChunked": False,
        "bm25Indexed": False,
        "balanceSheetAvailable": False,
        "balanceSheetPartial": False,
        "balanceSheetSource": "unavailable",
        "balanceSheetPeriodEnd": None,
        "balanceSheetWarnings": [],
        "balanceSheetQualityScore": None,
        "balanceSheetRiskPenalty": None,
        "liquidityScore": None,
        "leverageScore": None,
        "solvencyScore": None,
        "triggeredBalanceSheetGates": [],
        "scoringInputsAvailable": False,
        "scoringAvailable": False,
        "officialSignal": None,
        "insufficientEvidenceReason": None,
        "latestFilingDate": None,
        "latestScoringDate": None,
        "lastPipelineRun": run_at,
    }


def _load_universe_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("records") or payload
    if not isinstance(rows, list):
        raise ValueError("Universe file must contain a list or records array")
    return rows


def _securities_from_universe_file(path: Path, limit: int | None = None, offset: int = 0,
                                   ticker: str | None = None, tickers: list[str] | None = None,
                                   exchange: str | None = None) -> list[Security]:
    rows = _load_universe_records(path)
    wanted = {value.upper() for value in (tickers or [])}
    if ticker:
        wanted.add(ticker.upper())
    supported_rows = [row for row in rows if row.get("isSupported", True)]
    if wanted:
        supported_rows = [row for row in supported_rows if str(row.get("ticker", "")).upper() in wanted]
    if exchange:
        supported_rows = [row for row in supported_rows if str(row.get("exchange") or "").upper() == exchange.upper()]
    securities: list[Security] = []
    for row in supported_rows[offset:]:
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


def _forms_available(facts: list[Any]) -> tuple[bool, bool, str | None]:
    recent_10k = any(fact.form == "10-K" for fact in facts)
    recent_10q = any(fact.form == "10-Q" for fact in facts)
    latest = max((fact.filed for fact in facts if fact.filed), default=None)
    return recent_10k, recent_10q, latest


def _coverage_report(*, universe_records: list[dict[str, Any]], signals: dict[str, Any],
                     status_by_ticker: dict[str, dict[str, Any]], errors: list[dict[str, str]],
                     run_at: str) -> dict[str, Any]:
    supported = [row for row in universe_records if row.get("isSupported", True)]
    nyse_nasdaq = [row for row in universe_records if str(row.get("exchange") or "").upper() in {"NYSE", "NASDAQ"}]
    signal_rows = signals.get("records", [])
    scoreable = [row for row in signal_rows if row.get("confidence") != "Insufficient"]
    insufficient = [row for row in signal_rows if row.get("confidence") == "Insufficient" or row.get("signal") == "insufficient-evidence"]
    unsupported_reasons: dict[str, int] = {}
    for row in universe_records:
        if row.get("isSupported", True):
            continue
        reason = row.get("excludeReason") or "unsupported"
        unsupported_reasons[reason] = unsupported_reasons.get(reason, 0) + 1
    failures_by_stage: dict[str, int] = {}
    for error in errors:
        stage = error.get("stage") or "unknown"
        failures_by_stage[stage] = failures_by_stage.get(stage, 0) + 1
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": run_at,
        "counts": {
            "raw_sec_symbols": len(universe_records),
            "unique_ciks": len({row.get("cik") for row in universe_records if row.get("cik")}),
            "listed_nyse_nasdaq_symbols": len(nyse_nasdaq),
            "supported_operating_companies": len(supported),
            "recent_10k_available": sum(1 for status in status_by_ticker.values() if status.get("recent10KAvailable")),
            "recent_10q_available": sum(1 for status in status_by_ticker.values() if status.get("recent10QAvailable")),
            "filings_downloaded": sum(1 for status in status_by_ticker.values() if status.get("filingsDownloaded")),
            "filings_indexed": sum(1 for status in status_by_ticker.values() if status.get("bm25Indexed")),
            "searchable_companies": sum(1 for status in status_by_ticker.values() if status.get("bm25Indexed")),
            "companyfacts_available": sum(1 for status in status_by_ticker.values() if status.get("companyFactsAvailable")),
            "scoreable_companies": len(scoreable),
            "insufficient_evidence_companies": len(insufficient),
            "unsupported_symbols": sum(1 for row in universe_records if not row.get("isSupported", True)),
            "failed_symbols": len(errors),
        },
        "unsupportedReasons": dict(sorted(unsupported_reasons.items())),
        "failuresByStage": dict(sorted(failures_by_stage.items())),
        "failedSymbols": errors,
        "insufficientEvidence": [
            {
                "ticker": row["ticker"],
                "reason": status_by_ticker.get(row["ticker"], {}).get("insufficientEvidenceReason") or "Insufficient scoring inputs",
            }
            for row in insufficient
        ],
    }


def _balance_sheet_scoring_report(signals: dict[str, Any], mode: str) -> dict[str, Any]:
    records = signals.get("records", [])
    with_scoring = [row for row in records if row.get("balanceSheetScoringShadow")]
    changed = []
    liquidity = leverage = negative_equity = maturity = 0
    for row in with_scoring:
        scoring = row.get("balanceSheetScoringShadow") or {}
        gates = [gate for gate in scoring.get("triggeredRiskGates", []) if gate.get("triggered")]
        names = {gate.get("name") for gate in gates}
        liquidity += "Liquidity Risk Gate" in names or "Severe Liquidity Risk Gate" in names
        leverage += "High Leverage Gate" in names or "Severe Leverage Gate" in names
        negative_equity += "Negative Equity Gate" in names
        maturity += "Debt Maturity Pressure Gate" in names
        impact = scoring.get("experimentalSignalImpact") or row.get("experimentalBalanceSheetAdjustedSignal") or {}
        if impact.get("wouldChangeSignal") or impact.get("changed") or (row.get("balanceSheetOfficialChange") or {}).get("changed"):
            changed.append({
                "ticker": row.get("ticker"),
                "oldSignal": (row.get("balanceSheetOfficialChange") or {}).get("previousOfficialSignal") or impact.get("currentOfficialSignal") or impact.get("previousOfficialSignal"),
                "newSignal": (row.get("balanceSheetOfficialChange") or {}).get("newSignal") or impact.get("experimentalSignal") or impact.get("signal"),
                "triggeredGates": [gate.get("name") for gate in gates],
                "reason": impact.get("reason") or "; ".join(impact.get("reasons") or []),
            })
    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": mode,
        "companiesWithBalanceSheetScores": len(with_scoring),
        "companiesWithLiquidityRisk": liquidity,
        "companiesWithHighLeverage": leverage,
        "companiesWithNegativeEquity": negative_equity,
        "companiesWithDebtMaturityPressure": maturity,
        "companiesWhereExperimentalSignalWouldChange": len(changed),
        "companiesWhereOfficialSignalStayedStable": len(with_scoring) - len(changed) if mode == "official" else len(with_scoring),
        "changes": changed,
    }


def run(price_provider: PriceProvider, facts_provider: CompanyFactsProvider, output_dir: Path,
        limit: int | None = None, securities: list[Security] | None = None,
        include_backtest: bool = True, universe_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    run_at = started.isoformat()
    rows: list[dict[str, Any]] = []
    feature_rows: list[dict[str, Any]] = []
    balance_sheet_bundles: dict[str, dict[str, Any]] = {}
    price_history: dict[str, list[Any]] = {}
    fact_history: dict[str, list[Any]] = {}
    errors: list[dict[str, str]] = []
    ticker_reports: list[dict[str, Any]] = []
    status_by_ticker: dict[str, dict[str, Any]] = {}
    universe = securities if securities is not None else build_universe(limit)
    universe_records = universe_records or [
        {"ticker": security.ticker, "cik": security.cik, "companyName": security.company_name, "exchange": security.exchange, "isSupported": True}
        for security in universe
    ]
    for security in universe:
        began = perf_counter()
        report: dict[str, Any] = {"ticker": security.ticker, "status": "success", "priceRows": 0, "financialFacts": 0}
        data_status = _empty_status(run_at)
        try:
            prices = price_provider.fetch(security.ticker)
            facts = normalize_company_facts(facts_provider.fetch(security.cik))
            recent_10k, recent_10q, latest_filing = _forms_available(facts)
            data_status.update({
                "submissionsAvailable": True,
                "companyFactsAvailable": bool(facts),
                "recent10KAvailable": recent_10k,
                "recent10QAvailable": recent_10q,
                "latestFilingDate": latest_filing,
            })
            price_history[security.ticker] = prices
            fact_history[security.ticker] = facts
            latest = latest_facts(facts)
            report.update(priceRows=len(prices), financialFacts=len(facts))
            shares_fact = latest.get("Shares outstanding")
            latest_price = prices[-1].close if prices else None
            market_cap = latest_price * shares_fact.value if latest_price and shares_fact else None
            bundle = balance_sheet_bundle(security, facts, market_cap=market_cap, shares_outstanding=shares_fact.value if shares_fact else None)
            balance_sheet_bundles[security.ticker] = bundle
            bs_snapshot = bundle["snapshot"]
            bs_scoring = bundle["scoring"]
            triggered_gates = [gate["name"] for gate in bs_scoring.get("triggeredRiskGates", []) if gate.get("triggered")]
            data_status.update({
                "balanceSheetAvailable": bs_snapshot.get("source") != "unavailable" and not bs_snapshot.get("missingFields"),
                "balanceSheetPartial": bs_snapshot.get("source") != "unavailable" and bool(bs_snapshot.get("missingFields")),
                "balanceSheetSource": bs_snapshot.get("source"),
                "balanceSheetPeriodEnd": bs_snapshot.get("periodEndDate"),
                "balanceSheetWarnings": bs_scoring.get("warnings", [])[:8],
                "balanceSheetQualityScore": bs_scoring.get("balanceSheetQualityScore"),
                "balanceSheetRiskPenalty": bs_scoring.get("balanceSheetRiskPenalty"),
                "liquidityScore": bs_scoring.get("liquidityScore"),
                "leverageScore": bs_scoring.get("leverageScore"),
                "solvencyScore": bs_scoring.get("solvencyScore"),
                "triggeredBalanceSheetGates": triggered_gates,
            })
            raw_features = calculate_raw_features(prices, facts)
            derived = derive_fields(prices, latest)
            if raw_features.get("revenue_growth") is not None:
                derived["revenueGrowthPercent"] = round(raw_features["revenue_growth"] * 100, 4)
            if raw_features.get("gross_margin") is not None:
                derived["grossMarginPercent"] = round(raw_features["gross_margin"] * 100, 4)
            if raw_features.get("net_margin") is not None:
                derived["netMarginPercent"] = round(raw_features["net_margin"] * 100, 4)
            if raw_features.get("latest_revenue") is not None:
                derived["latestRevenueBillions"] = round(raw_features["latest_revenue"] / 1_000_000_000, 4)
            detail_row = {
                "security": record(security),
                "derived": derived,
                "latestFacts": {name: record(fact) for name, fact in latest.items()},
                "balanceSheet": bs_snapshot,
                "balanceSheetMetrics": bundle["metrics"],
                "balanceSheetScoringShadow": bs_scoring,
                "priceHistory": [record(bar) for bar in prices[-PRICE_HISTORY_EXPORT_SESSIONS:]],
                "dataStatus": data_status,
            }
            write_json(output_dir / "stocks" / f"{security.ticker}.json", {"schemaVersion": SCHEMA_VERSION, "generatedAt": datetime.now(timezone.utc).isoformat(), "record": detail_row})
            rows.append({"security": record(security), "derived": detail_row["derived"], "dataStatus": data_status, "balanceSheetScoringShadow": bs_scoring})
            feature_rows.append({"ticker": security.ticker, "asOf": prices[-1].date, "raw": raw_features, "balanceSheetScoring": bs_scoring})
        except Exception as exc:
            report["status"] = "failed"
            report["error"] = f"{type(exc).__name__}: {exc}"
            data_status["insufficientEvidenceReason"] = report["error"]
            errors.append({"ticker": security.ticker, "stage": "ticker_pipeline", "message": report["error"]})
        finally:
            report["durationMs"] = round((perf_counter() - began) * 1000)
            report["dataStatus"] = data_status
            status_by_ticker[security.ticker] = data_status
            ticker_reports.append(report)
    finished = datetime.now(timezone.utc)
    dashboard = {"schemaVersion": SCHEMA_VERSION, "generatedAt": finished.isoformat(), "mode": "live", "records": rows}
    normalized_features = normalize_universe(feature_rows)
    features = {"schemaVersion": FEATURE_SCHEMA_VERSION, "generatedAt": finished.isoformat(), "universeSize": len(feature_rows), "records": normalized_features}
    signals = {"schemaVersion": SCORE_SCHEMA_VERSION, "generatedAt": finished.isoformat(), "universeSize": len(feature_rows), "records": score_universe(normalized_features)}
    bs_mode = balance_sheet_scoring_mode()
    for signal in signals["records"]:
        status = status_by_ticker.setdefault(signal["ticker"], _empty_status(run_at))
        bs_scoring = signal.get("balanceSheetScoringShadow") or {}
        bs_impact = bs_scoring.get("experimentalSignalImpact") or experimental_signal(signal.get("signal"), signal.get("scores", {}), bs_scoring) if bs_scoring else {}
        status.update({
            "scoringInputsAvailable": signal.get("availableFeatures", 0) >= 5,
            "scoringAvailable": signal.get("confidence") != "Insufficient",
            "officialSignal": signal.get("signal"),
            "latestScoringDate": signal.get("asOf"),
            "insufficientEvidenceReason": "Insufficient scoring inputs" if signal.get("confidence") == "Insufficient" else None,
            "balanceSheetExperimentalSignal": bs_impact.get("experimentalSignal") or bs_impact.get("signal"),
            "balanceSheetWouldChangeSignal": bs_impact.get("wouldChangeSignal") if "wouldChangeSignal" in bs_impact else bs_impact.get("changed"),
        })
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
    coverage = _coverage_report(universe_records=universe_records, signals=signals, status_by_ticker=status_by_ticker,
                                errors=errors, run_at=finished.isoformat())
    balance_sheet_report = write_balance_sheet_artifacts(balance_sheet_bundles)
    scoring_report = _balance_sheet_scoring_report(signals, bs_mode)
    report_root = Path("data") / "reports"
    report_root.mkdir(parents=True, exist_ok=True)
    if bs_mode == "official":
        write_json(report_root / "balance_sheet_scoring_official_change_report.json", scoring_report)
    elif bs_mode == "experimental":
        write_json(report_root / "balance_sheet_scoring_experimental_report.json", scoring_report)
    else:
        write_json(report_root / "balance_sheet_scoring_shadow_report.json", scoring_report)
    coverage["counts"].update({
        "balance_sheets_available": balance_sheet_report["balanceSheetsAvailable"],
        "balance_sheets_partial": balance_sheet_report["balanceSheetsPartial"],
        "balance_sheets_unavailable": balance_sheet_report["unavailableCompanies"],
    })
    active_tickers = {row["security"]["ticker"].upper() for row in rows}
    stale_stock_artifacts_removed = remove_stale_stock_artifacts(output_dir, active_tickers)
    audit = {
        "schemaVersion": SCHEMA_VERSION,
        "runStartedAt": started.isoformat(),
        "runFinishedAt": finished.isoformat(),
        "status": "success" if not errors else "partial_success",
        "requestedTickers": len(ticker_reports),
        "successfulTickers": len(rows),
        "failedTickers": len(errors),
        "staleStockArtifactsRemoved": stale_stock_artifacts_removed,
        "errors": errors,
        "tickers": ticker_reports,
        "coverageCounts": coverage["counts"],
        "balanceSheetCoverage": balance_sheet_report,
    }
    summary = {"schemaVersion": SCHEMA_VERSION, "generatedAt": finished.isoformat(), "records": [
        {
            "ticker": row["security"]["ticker"],
            "companyName": row["security"]["company_name"],
            "exchange": row["security"]["exchange"],
            "sector": row["security"].get("sector"),
            "derived": row["derived"],
            "dataStatus": status_by_ticker.get(row["security"]["ticker"], _empty_status(run_at)),
        } for row in rows
    ]}
    write_json(output_dir / "dashboard.json", dashboard)
    write_json(output_dir / "stocks" / "summary.json", summary)
    write_json(output_dir / "features.json", features)
    write_json(output_dir / "signals.json", signals)
    write_json(output_dir / "backtest_results.json", backtest)
    write_json(output_dir / "etl_report.json", audit)
    write_json(output_dir / "universe_coverage_report.json", coverage)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ValueSignal market and SEC ETL pipeline")
    parser.add_argument("--output", type=Path, default=Path("public/data"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--ticker")
    parser.add_argument("--tickers", nargs="*")
    parser.add_argument("--exchange")
    parser.add_argument("--mode", default="starter", help="accepted for scaled command compatibility; use --universe for non-starter rows")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--sleep-ms", type=int, default=200)
    parser.add_argument("--universe", type=Path, help="Optional scaled universe JSON from scripts/universe/build_universe.py")
    parser.add_argument("--skip-backtest", action="store_true", help="Write a small unavailable backtest report for scaled runs")
    args = parser.parse_args()
    user_agent = os.getenv("VS_USER_AGENT", "")
    if not user_agent or "@" not in user_agent:
        print("VS_USER_AGENT must identify the application and include a contact email.", file=sys.stderr)
        return 2
    universe_records = _load_universe_records(args.universe) if args.universe else None
    securities = _securities_from_universe_file(args.universe, args.limit, args.offset, args.ticker, args.tickers, args.exchange) if args.universe else None
    if args.dry_run:
        print(f"DRY RUN: {len(securities or build_universe(args.limit))} tickers would be processed")
        return 0
    audit = run(YahooChartPriceProvider(user_agent, range_name="5y"), SecCompanyFactsProvider(user_agent), args.output,
                args.limit, securities, include_backtest=not args.skip_backtest, universe_records=universe_records)
    print(f"ETL {audit['status']}: {audit['successfulTickers']}/{audit['requestedTickers']} tickers published")
    print("Coverage counts:", json.dumps(audit["coverageCounts"], sort_keys=True))
    return 0 if audit["successfulTickers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
