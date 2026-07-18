import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.forecast.pipeline import TRAINING_DATASET_PATH, build_training_rows, now_iso, write_json


def main() -> int:
    rows = build_training_rows()
    write_json(TRAINING_DATASET_PATH, {"schemaVersion": "1.0.0", "generatedAt": now_iso(), "rows": rows})
    print(f"FORECAST TRAINING DATASET: wrote {len(rows)} rows to {TRAINING_DATASET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
