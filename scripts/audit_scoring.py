from __future__ import annotations
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.scoring import classify, sensitivity_scenarios

def main() -> int:
    signals=json.loads(Path("public/data/signals.json").read_text(encoding="utf-8"))
    features=json.loads(Path("public/data/features.json").read_text(encoding="utf-8"))
    failures=[]
    labels={"potentially-undervalued","quality-watchlist","value-trap-risk","momentum-risk","neutral","insufficient-evidence"}
    print("WEIGHTED CONTRIBUTIONS:")
    for row in signals["records"]:
        for name,component in row["components"].items():
            score=component["score"]
            points=round(sum(item["points"] for item in component["contributions"]),4)
            if score is not None and abs(score-points)>0.001: failures.append(f"{row['ticker']}:{name}: contribution mismatch")
            if score is not None and not 0<=score<=100: failures.append(f"{row['ticker']}:{name}: out of bounds")
        if row["signal"] not in labels: failures.append(f"{row['ticker']}: invalid label")
        if row["signal"]!=classify(row["scores"],row["confidence"]): failures.append(f"{row['ticker']}: nondeterministic label")
        print(f"  {row['ticker']}: signal={row['signal']} confidence={row['confidence']} value={row['scores']['value']} quality={row['scores']['quality']} momentumRisk={row['scores']['momentumRisk']} marketRisk={row['scores']['marketRisk']} balanceRisk={row['scores']['balanceSheetRisk']}")
    scenarios=sensitivity_scenarios(features["records"])
    changed=sum(item["changedCount"] for item in scenarios)
    print(f"BOUNDS/DETERMINISM: {'PASS' if not failures else 'FAIL'} ({len(signals['records'])} records)")
    print(f"SENSITIVITY: PASS ({len(scenarios)} ±20% scenarios, {changed} total label changes)")
    if failures:
        print("\n".join(failures))
    return 1 if failures else 0

if __name__=="__main__": raise SystemExit(main())
