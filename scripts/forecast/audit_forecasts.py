import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.forecast.pipeline import FORECAST_DIR


def ordered(horizon: dict) -> bool:
    values = [horizon.get("lowerReturn"), horizon.get("returnEstimate"), horizon.get("upperReturn")]
    return all(isinstance(value, (int, float)) and math.isfinite(value) for value in values) and values[0] <= values[1] <= values[2] and values[0] > -1


def main() -> int:
    files = sorted(path for path in FORECAST_DIR.glob("*.json") if path.name != "summary.json")
    failures = []
    for path in files:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if not ordered(artifact.get("horizon30Day", {})):
            failures.append(f"{path.name}: invalid 30-day range")
        if not ordered(artifact.get("horizon90Day", {})):
            failures.append(f"{path.name}: invalid 90-day range")
        if artifact.get("analystTarget", {}).get("status") == "available" and artifact["analystTarget"].get("horizonDays") in (30, 90):
            failures.append(f"{path.name}: analyst target incorrectly treated as short-horizon model estimate")
    print(json.dumps({"status": "PASS" if not failures else "FAIL", "forecastFiles": len(files), "failures": failures[:20]}, indent=2))
    return 0 if not failures and files else 1


if __name__ == "__main__":
    raise SystemExit(main())
