import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.forecast.pipeline import build_training_rows, evaluate_horizon


def main() -> int:
    rows = build_training_rows()
    results = {30: evaluate_horizon(rows, 30), 90: evaluate_horizon(rows, 90)}
    print(json.dumps({str(horizon): {"selectedModel": result["selectedModelName"], "validationStatus": "experimental"} for horizon, result in results.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
