import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.forecast.pipeline import FEATURE_COLUMNS, TRAINING_DATASET_PATH, build_training_rows, finite, quality_report, write_json, QUALITY_PATH


def main() -> int:
    rows = build_training_rows()
    report = quality_report(rows)
    write_json(TRAINING_DATASET_PATH, {"schemaVersion": "1.0.0", "generatedAt": report["generatedAt"], "rows": rows})
    write_json(QUALITY_PATH, report)
    required_ok = bool(rows) and report["labeled30DayRows"] > 0 and report["labeled90DayRows"] > 0
    finite_current = all(finite(row.get("currentAdjustedClose")) for row in rows)
    feature_presence = {name: sum(finite(row.get(name)) for row in rows) for name in FEATURE_COLUMNS}
    print(json.dumps({"status": "PASS" if required_ok and finite_current else "FAIL", "quality": report, "featurePresence": feature_presence}, indent=2))
    return 0 if required_ok and finite_current else 1


if __name__ == "__main__":
    raise SystemExit(main())
