from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("data/reports/scoring_baseline_before_balance_sheet_integration.json")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(path: Path) -> list[dict[str, Any]]:
    payload = _load(path)
    rows = payload.get("records", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a records array")
    return rows


def _by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("ticker") or row.get("security", {}).get("ticker", "")).upper(): row for row in rows}


def build_baseline(
    *,
    signals_path: Path = Path("public/data/signals.json"),
    dashboard_path: Path = Path("public/data/dashboard.json"),
    features_path: Path = Path("public/data/features.json"),
) -> dict[str, Any]:
    signals_payload = _load(signals_path)
    generated_at = datetime.now(timezone.utc).isoformat()
    dashboard_by_ticker = _by_ticker(_records(dashboard_path))
    features_by_ticker = _by_ticker(_records(features_path))
    records: list[dict[str, Any]] = []

    for row in signals_payload.get("records", []):
        ticker = str(row.get("ticker", "")).upper()
        dashboard = dashboard_by_ticker.get(ticker, {})
        feature = features_by_ticker.get(ticker, {})
        security = dashboard.get("security") or {}
        scores = row.get("scores") or {}
        raw = feature.get("raw") or {}
        records.append({
            "ticker": ticker,
            "companyName": security.get("company_name") or row.get("companyName") or ticker,
            "officialSignal": row.get("signal"),
            "valueScore": scores.get("value"),
            "qualityScore": scores.get("quality"),
            "riskScore": scores.get("marketRisk"),
            "marketRiskScore": scores.get("marketRisk"),
            "balanceSheetRiskScore": scores.get("balanceSheetRisk"),
            "momentumRiskScore": scores.get("momentumRisk"),
            "confidenceScore": row.get("confidence"),
            "liabilitiesToAssets": raw.get("liabilities_to_assets") or (dashboard.get("derived") or {}).get("liabilitiesToAssets"),
            "dataStatus": dashboard.get("dataStatus") or {},
            "timestamp": generated_at,
            "scoringSchemaVersion": row.get("scoreVersion") or signals_payload.get("schemaVersion"),
        })

    return {
        "schemaVersion": "1.0.0",
        "generatedAt": generated_at,
        "source": {
            "signals": str(signals_path),
            "dashboard": str(dashboard_path),
            "features": str(features_path),
        },
        "scoreConvention": {
            "valueScore": "higher_is_stronger",
            "qualityScore": "higher_is_stronger",
            "momentumRiskScore": "higher_is_riskier",
            "marketRiskScore": "higher_is_riskier",
            "balanceSheetRiskScore": "higher_is_riskier",
        },
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the scoring-v1 baseline before balance-sheet scoring integration.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--signals", type=Path, default=Path("public/data/signals.json"))
    parser.add_argument("--dashboard", type=Path, default=Path("public/data/dashboard.json"))
    parser.add_argument("--features", type=Path, default=Path("public/data/features.json"))
    args = parser.parse_args()

    payload = build_baseline(signals_path=args.signals, dashboard_path=args.dashboard, features_path=args.features)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['records'])} scoring baseline rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
