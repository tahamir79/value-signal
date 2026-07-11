from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.build_universe import build_universe as build_starter_universe
from scripts.universe.normalize_symbols import normalize_cik, normalize_ticker, stable_universe_key
from scripts.universe.universe_filters import classify_security
from scripts.universe.universe_manifest import build_manifest


SEC_TICKER_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
UNIVERSE_MODES = {"starter", "watchlist", "sp500_or_largecap", "largecap", "nyse", "nasdaq", "nyse_nasdaq_core", "sec_listed_core", "sec_listed_all", "sec_traceable_all", "custom"}


def default_data_status() -> dict[str, bool]:
    return {
        "rawSecTraceable": True,
        "submissionsAvailable": False,
        "companyFactsAvailable": False,
        "recent10KAvailable": False,
        "recent10QAvailable": False,
        "recent8KAvailable": False,
        "filingsIndexed": False,
        "bm25Indexed": False,
        "scoringInputsAvailable": False,
        "scoringAvailable": False,
        "officialSignal": None,
        "insufficientEvidenceReason": None,
        "latestFilingDate": None,
        "latestScoringDate": None,
        "lastPipelineRun": None,
    }


def universe_row(cik: int | str, ticker: str, company_name: str, exchange: str | None,
                 *, force_supported: bool = False) -> dict[str, Any]:
    normalized_cik = normalize_cik(cik)
    normalized_ticker = normalize_ticker(ticker)
    decision = classify_security(normalized_ticker, company_name, exchange)
    if force_supported:
        decision = type(decision)(True, support_reason="starter universe seed", exclude_reason=None, priority=0)
    return {
        "cik": normalized_cik,
        "ticker": normalized_ticker,
        "companyName": company_name,
        "exchange": exchange,
        "sector": None,
        "industry": None,
        "securityType": None,
        "isSupported": decision.is_supported,
        "supportReason": decision.support_reason,
        "excludeReason": decision.exclude_reason,
        "priority": decision.priority,
        "dataStatus": default_data_status(),
    }


def load_sec_mapping(user_agent: str, source_url: str = SEC_TICKER_EXCHANGE_URL) -> list[dict[str, Any]]:
    request = Request(source_url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    fields = payload.get("fields") or []
    data = payload.get("data") or []
    return [dict(zip(fields, row)) for row in data]


def rows_from_starter(limit: int | None = None) -> list[dict[str, Any]]:
    return [
        universe_row(item.cik, item.ticker, item.company_name, item.exchange, force_supported=True)
        for item in build_starter_universe(limit)
    ]


def rows_from_sec_mapping(records: list[dict[str, Any]], *, mode: str, limit: int | None = None,
                          offset: int = 0, exchange: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    wanted_exchange = exchange.upper() if exchange else None
    for record in records:
        row = universe_row(record.get("cik"), record.get("ticker"), record.get("name"), record.get("exchange"))
        if wanted_exchange and str(row.get("exchange") or "").upper() != wanted_exchange:
            continue
        if mode == "nyse" and str(row.get("exchange") or "").upper() != "NYSE":
            continue
        if mode == "nasdaq" and str(row.get("exchange") or "").upper() != "NASDAQ":
            continue
        key = stable_universe_key(row["cik"], row["ticker"])
        if key in seen:
            row["isSupported"] = False
            row["excludeReason"] = "duplicate CIK/ticker row"
        seen.add(key)
        if mode in {"sec_listed_core", "nyse_nasdaq_core", "nyse", "nasdaq", "largecap"} and not row["isSupported"]:
            rows.append(row)
            continue
        rows.append(row)
    rows.sort(key=lambda row: (0 if row["isSupported"] else 1, row.get("priority", 100), row["ticker"]))
    if limit:
        supported = [row for row in rows if row["isSupported"]][offset:offset + limit]
        unsupported = [row for row in rows if not row["isSupported"]]
        return supported + unsupported[: max(0, min(len(unsupported), limit - len(supported)))]
    if offset:
        supported = [row for row in rows if row["isSupported"]][offset:]
        unsupported = [row for row in rows if not row["isSupported"]]
        return supported + unsupported
    return rows


def build_scaled_universe(*, mode: str, limit: int | None = None, user_agent: str | None = None,
                          sec_records: list[dict[str, Any]] | None = None, offset: int = 0,
                          exchange: str | None = None) -> list[dict[str, Any]]:
    if mode not in UNIVERSE_MODES:
        raise ValueError(f"unsupported universe mode: {mode}")
    if mode in {"starter", "watchlist", "custom", "sp500_or_largecap", "largecap"} and sec_records is None:
        return rows_from_starter(limit)
    records = sec_records if sec_records is not None else load_sec_mapping(user_agent or required_user_agent())
    return rows_from_sec_mapping(records, mode=mode, limit=limit, offset=offset, exchange=exchange)


def required_user_agent() -> str:
    user_agent = os.getenv("VS_USER_AGENT") or os.getenv("SEC_USER_AGENT")
    if not user_agent:
        raise RuntimeError("Set VS_USER_AGENT with an identifying contact before SEC requests.")
    return user_agent


def write_universe(rows: list[dict[str, Any]], *, mode: str, limit: int | None, output_dir: Path,
                   source: str = SEC_TICKER_EXCHANGE_URL, dry_run: bool = False) -> dict[str, Any]:
    manifest = build_manifest(mode=mode, requested_limit=limit, rows=rows, source=source)
    if dry_run:
        return manifest
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "universe.json").write_text(json.dumps({"records": rows}, indent=2) + "\n", encoding="utf-8")
    (output_dir / "universe_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a staged ValueSignal stock universe.")
    parser.add_argument("--mode", choices=sorted(UNIVERSE_MODES), default="starter")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--exchange")
    parser.add_argument("--output-dir", default="data/universe")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="reserved for compatibility with scaled jobs")
    parser.add_argument("--resume", action="store_true", help="reserved for compatibility with scaled jobs")
    parser.add_argument("--sleep-ms", type=int, default=200)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--ticker")
    parser.add_argument("--tickers", nargs="*")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_scaled_universe(mode=args.mode, limit=args.limit, offset=args.offset, exchange=args.exchange)
    manifest = write_universe(rows, mode=args.mode, limit=args.limit, output_dir=Path(args.output_dir), dry_run=args.dry_run)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
