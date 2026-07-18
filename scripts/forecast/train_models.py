import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.forecast.pipeline import build_training_rows, evaluate_horizon


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, choices=[30, 90], required=True)
    args = parser.parse_args()
    result = evaluate_horizon(build_training_rows(), args.horizon)
    print(json.dumps({"horizonDays": args.horizon, "selectedModel": result["selectedModelName"], "split": result["split"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
