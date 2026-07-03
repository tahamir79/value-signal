from __future__ import annotations

import json
from pathlib import Path


def audit(path: Path = Path("public/data/backtest_results.json")) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    observations = data.get("observations", [])
    for row in observations:
        source_dates = [row.get("availableAt"), row.get("sourcePriceThrough"), row.get("sourceMaxFiledAt")]
        if any(value and value > row["signalDate"] for value in source_dates):
            failures.append(f"future input: {row['ticker']} {row['signalDate']}")
        if not row["signalDate"] < row["entryDate"] < row["outcomeDate"]:
            failures.append(f"outcome ordering: {row['ticker']} {row['signalDate']}")
        if not isinstance(row.get("benchmarkReturn"), (int, float)):
            failures.append(f"benchmark alignment missing: {row['ticker']} {row['signalDate']}")
    all_cohorts = [row for row in data.get("cohorts", []) if row.get("marketRegime") == "all"]
    if sum(row.get("sampleCount", 0) for row in all_cohorts) != len(observations):
        failures.append("cohort sample counts do not reconcile to observations")
    if data.get("evaluatedObservationCount") != len(observations):
        failures.append("evaluated observation count does not reconcile")
    print(f"POINT-IN-TIME INPUTS: {'PASS' if not any('future input' in item for item in failures) else 'FAIL'} ({len(observations)} observations)")
    print(f"SIGNAL BEFORE OUTCOME: {'PASS' if not any('outcome ordering' in item for item in failures) else 'FAIL'}")
    print(f"BENCHMARK DATE ALIGNMENT: {'PASS' if not any('benchmark alignment' in item for item in failures) else 'FAIL'}")
    print(f"SAMPLE COUNTS: {'PASS' if not any('count' in item for item in failures) else 'FAIL'} ({len(all_cohorts)} all-regime cohorts)")
    print(f"OVERLAPPING WINDOWS: REPORTED ({data.get('biasAudit', {}).get('overlappingWindows', 0)})")
    print(f"MISSING/DELISTED SYMBOL PROXY: REPORTED ({len(data.get('biasAudit', {}).get('missingExpectedSymbols', []))})")
    trace = data.get("traceObservation")
    print(f"TRACE OBSERVATION: {'PASS' if trace or data.get('status') == 'insufficient_data' else 'FAIL'}")
    if data.get("status") == "insufficient_data":
        print("RESULT STATUS: AWAITING POINT-IN-TIME HISTORY (no performance claim published)")
    return failures


if __name__ == "__main__":
    problems = audit()
    if problems:
        print("\n".join(problems))
    raise SystemExit(1 if problems else 0)
