from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_BASELINE = Path("data/reports/scoring_baseline_before_balance_sheet_integration.json")
DEFAULT_CURRENT = Path("public/data/signals.json")
DEFAULT_OUTPUT = Path("data/reports/scoring_comparison_report.json")


SCORE_FIELDS = {
    "valueScore": ("scores", "value"),
    "qualityScore": ("scores", "quality"),
    "riskScore": ("scores", "marketRisk"),
    "marketRiskScore": ("scores", "marketRisk"),
    "balanceSheetRiskScore": ("scores", "balanceSheetRisk"),
    "momentumRiskScore": ("scores", "momentumRisk"),
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _records(path: Path) -> list[dict[str, Any]]:
    payload = _load(path)
    rows = payload.get("records", [])
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a records array")
    return rows


def _ticker(row: dict[str, Any]) -> str:
    return str(row.get("ticker") or row.get("security", {}).get("ticker", "")).upper()


def _score(row: dict[str, Any], baseline_field: str) -> Any:
    parent, key = SCORE_FIELDS[baseline_field]
    value = row.get(parent, {})
    return value.get(key) if isinstance(value, dict) else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _score_change(before: Any, after: Any) -> float | None:
    left, right = _number(before), _number(after)
    return round(right - left, 4) if left is not None and right is not None else None


def _gate_names(row: dict[str, Any]) -> list[str]:
    scoring = row.get("balanceSheetScoringShadow") or row.get("balanceSheetScoring") or {}
    gates = scoring.get("triggeredRiskGates") or row.get("triggeredBalanceSheetGates") or []
    names = []
    for gate in gates:
        if isinstance(gate, dict):
            if gate.get("triggered", True):
                names.append(str(gate.get("name") or gate.get("id") or "unnamed_gate"))
        else:
            names.append(str(gate))
    return sorted(set(names))


def compare(
    baseline_path: Path = DEFAULT_BASELINE,
    current_path: Path = DEFAULT_CURRENT,
    *,
    large_move_threshold: float = 15.0,
) -> dict[str, Any]:
    baseline_payload = _load(baseline_path)
    baseline_rows = {_ticker(row): row for row in baseline_payload.get("records", [])}
    current_rows = {_ticker(row): row for row in _records(current_path)}

    signal_changes: list[dict[str, Any]] = []
    score_changes: list[dict[str, Any]] = []
    confidence_changes: list[dict[str, Any]] = []
    large_movements: list[dict[str, Any]] = []
    newly_triggered_balance_sheet_gates: list[dict[str, Any]] = []
    newly_marked_value_trap_risk: list[dict[str, Any]] = []
    newly_marked_insufficient_evidence: list[dict[str, Any]] = []
    missing_current_tickers: list[str] = []

    for ticker, before in sorted(baseline_rows.items()):
        after = current_rows.get(ticker)
        if not after:
            missing_current_tickers.append(ticker)
            continue

        before_signal = before.get("officialSignal")
        after_signal = after.get("signal") or after.get("officialSignal")
        if before_signal != after_signal:
            item = {"ticker": ticker, "before": before_signal, "after": after_signal}
            signal_changes.append(item)
            if after_signal == "value-trap-risk":
                newly_marked_value_trap_risk.append(item)
            if after_signal == "insufficient-evidence":
                newly_marked_insufficient_evidence.append(item)

        before_confidence = before.get("confidenceScore")
        after_confidence = after.get("confidence")
        if before_confidence != after_confidence:
            confidence_changes.append({"ticker": ticker, "before": before_confidence, "after": after_confidence})

        for baseline_field in SCORE_FIELDS:
            before_value = before.get(baseline_field)
            after_value = _score(after, baseline_field)
            delta = _score_change(before_value, after_value)
            if delta is None:
                if before_value != after_value:
                    score_changes.append({"ticker": ticker, "field": baseline_field, "before": before_value, "after": after_value, "delta": None})
                continue
            if delta:
                change = {"ticker": ticker, "field": baseline_field, "before": before_value, "after": after_value, "delta": delta}
                score_changes.append(change)
                if abs(delta) >= large_move_threshold:
                    large_movements.append(change)

        gates = _gate_names(after)
        if gates:
            newly_triggered_balance_sheet_gates.append({"ticker": ticker, "gates": gates})

    return {
        "schemaVersion": "1.0.0",
        "baseline": str(baseline_path),
        "current": str(current_path),
        "largeMoveThreshold": large_move_threshold,
        "counts": {
            "baselineRows": len(baseline_rows),
            "currentRows": len(current_rows),
            "signalChanges": len(signal_changes),
            "scoreChanges": len(score_changes),
            "confidenceChanges": len(confidence_changes),
            "newlyTriggeredBalanceSheetGateCompanies": len(newly_triggered_balance_sheet_gates),
            "newlyMarkedValueTrapRisk": len(newly_marked_value_trap_risk),
            "newlyMarkedInsufficientEvidence": len(newly_marked_insufficient_evidence),
            "largeMovements": len(large_movements),
            "missingCurrentTickers": len(missing_current_tickers),
        },
        "signalChanges": signal_changes,
        "scoreChanges": score_changes,
        "confidenceChanges": confidence_changes,
        "newlyTriggeredBalanceSheetGates": newly_triggered_balance_sheet_gates,
        "newlyMarkedValueTrapRisk": newly_marked_value_trap_risk,
        "newlyMarkedInsufficientEvidence": newly_marked_insufficient_evidence,
        "largeMovements": large_movements,
        "missingCurrentTickers": missing_current_tickers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare current scoring output against the pre-balance-sheet-integration baseline.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--large-move-threshold", type=float, default=15.0)
    args = parser.parse_args()

    report = compare(args.baseline, args.current, large_move_threshold=args.large_move_threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
