import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.forecast.pipeline import LEADERBOARD_PATH, BACKTEST_30_PATH, BACKTEST_90_PATH, build_training_rows, evaluate_horizon, now_iso, write_json


def main() -> int:
    rows = build_training_rows()
    results = {30: evaluate_horizon(rows, 30), 90: evaluate_horizon(rows, 90)}
    payload = {"schemaVersion": "1.0.0", "generatedAt": now_iso(), "models": results[30]["leaderboard"] + results[90]["leaderboard"]}
    write_json(LEADERBOARD_PATH, payload)
    write_json(BACKTEST_30_PATH, {"schemaVersion": "1.0.0", "generatedAt": payload["generatedAt"], "horizonDays": 30, "split": results[30]["split"], "selectedModel": results[30]["selectedModelName"], "leaderboard": results[30]["leaderboard"]})
    write_json(BACKTEST_90_PATH, {"schemaVersion": "1.0.0", "generatedAt": payload["generatedAt"], "horizonDays": 90, "split": results[90]["split"], "selectedModel": results[90]["selectedModelName"], "leaderboard": results[90]["leaderboard"]})
    print(json.dumps({"status": "PASS", "selected30": results[30]["selectedModelName"], "selected90": results[90]["selectedModelName"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
