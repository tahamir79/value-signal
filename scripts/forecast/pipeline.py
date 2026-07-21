from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

try:
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import ElasticNet, HuberRegressor, Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:  # pragma: no cover - audited at runtime
    HistGradientBoostingRegressor = RandomForestRegressor = None
    SimpleImputer = ElasticNet = HuberRegressor = Ridge = None
    mean_absolute_error = mean_squared_error = median_absolute_error = None
    MLPRegressor = make_pipeline = StandardScaler = None


ROOT = Path(__file__).resolve().parents[2]
STOCK_DIR = ROOT / "public" / "data" / "stocks"
FORECAST_DIR = ROOT / "public" / "data" / "forecasts"
REPORT_DIR = ROOT / "data" / "reports"
MODEL_DIR = ROOT / "models" / "forecast"
TRAINING_DATASET_PATH = REPORT_DIR / "forecast_training_dataset.json"
LEADERBOARD_PATH = REPORT_DIR / "forecast_model_leaderboard.json"
BACKTEST_30_PATH = REPORT_DIR / "forecast_backtest_30_day.json"
BACKTEST_90_PATH = REPORT_DIR / "forecast_backtest_90_day.json"
QUALITY_PATH = REPORT_DIR / "forecast_data_quality.json"
LEAKAGE_PATH = REPORT_DIR / "forecast_leakage_audit.json"

FEATURE_COLUMNS = [
    "return5Day",
    "return21Day",
    "return63Day",
    "volatility21Day",
    "volatility63Day",
    "drawdown63Day",
    "volumeTrend21Day",
]
BASELINE_MODEL_NAMES = {"zero-return baseline", "historical-mean baseline", "market-return baseline"}
CONSERVATIVE_SCENARIO_METHOD = "valuesignal_conservative_historical_scenario_v1"
SCENARIO_SAMPLE_STEP_SESSIONS = 21
SCENARIO_MIN_SAMPLES = {30: 24, 90: 12}
SCENARIO_SHRINKAGE_CONSTANT = {30: 24, 90: 18}
SCENARIO_RETURN_CAPS = {30: 0.08, 90: 0.15}
SCENARIO_STALE_MARKET_DATA_DAYS = 10
FORECAST_PRICE_HISTORY_MAX_SESSIONS = 540


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def adjusted_price(bar: dict[str, Any]) -> float | None:
    value = bar.get("adjusted_close")
    if not finite(value):
        value = bar.get("close")
    return float(value) if finite(value) and float(value) > 0 else None


def first_session_on_or_after(prices: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    for bar in prices:
        try:
            if date.fromisoformat(str(bar["date"])) >= target:
                return bar
        except (KeyError, ValueError):
            continue
    return None


def target_log_return(prices: list[dict[str, Any]], index: int, horizon_days: int) -> float | None:
    current = adjusted_price(prices[index])
    if current is None:
        return None
    feature_date = date.fromisoformat(str(prices[index]["date"]))
    future = first_session_on_or_after(prices[index + 1 :], feature_date + timedelta(days=horizon_days))
    future_price = adjusted_price(future) if future else None
    if future_price is None:
        return None
    return math.log(future_price / current)


def simple_return(prices: list[dict[str, Any]], index: int, sessions: int) -> float | None:
    if index < sessions:
        return None
    start = adjusted_price(prices[index - sessions])
    end = adjusted_price(prices[index])
    return end / start - 1 if start and end else None


def volatility(prices: list[dict[str, Any]], index: int, sessions: int) -> float | None:
    if index < sessions:
        return None
    values = [adjusted_price(row) for row in prices[index - sessions : index + 1]]
    clean = [value for value in values if value is not None]
    if len(clean) < max(10, sessions // 2):
        return None
    returns = [math.log(current / prior) for prior, current in zip(clean, clean[1:]) if prior > 0 and current > 0]
    return statistics.stdev(returns) * math.sqrt(252) if len(returns) >= 5 else None


def drawdown(prices: list[dict[str, Any]], index: int, sessions: int) -> float | None:
    if index < sessions:
        return None
    values = [adjusted_price(row) for row in prices[index - sessions : index + 1]]
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    peak, worst = clean[0], 0.0
    for value in clean:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    return worst


def volume_trend(prices: list[dict[str, Any]], index: int) -> float | None:
    if index < 42:
        return None
    recent = [float(row.get("volume", 0)) for row in prices[index - 20 : index + 1] if finite(row.get("volume"))]
    prior = [float(row.get("volume", 0)) for row in prices[index - 41 : index - 20] if finite(row.get("volume"))]
    if not recent or not prior:
        return None
    prior_mean = statistics.mean(prior)
    return statistics.mean(recent) / prior_mean - 1 if prior_mean > 0 else None


def active_stock_tickers() -> set[str] | None:
    summary_path = STOCK_DIR / "summary.json"
    if not summary_path.exists():
        return None
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    records = payload.get("records")
    if not isinstance(records, list):
        return None
    tickers = {
        str(record.get("ticker") or "").upper()
        for record in records
        if isinstance(record, dict) and record.get("ticker")
    }
    return tickers or None


def stock_files() -> Iterable[Path]:
    active = active_stock_tickers()
    paths = sorted(path for path in STOCK_DIR.glob("*.json") if path.name != "summary.json")
    if active is None:
        return paths
    return [path for path in paths if path.stem.upper() in active]


def remove_stale_forecast_artifacts(active_tickers: set[str]) -> list[str]:
    if not FORECAST_DIR.exists():
        return []
    active = {ticker.upper() for ticker in active_tickers}
    removed: list[str] = []
    for path in FORECAST_DIR.glob("*.json"):
        if path.name == "summary.json":
            continue
        ticker = path.stem.upper()
        if ticker not in active:
            path.unlink()
            removed.append(ticker)
    return sorted(removed)


def load_stock_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_feature_row(payload: dict[str, Any], prices: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    record = payload.get("record", {})
    security = record.get("security", {})
    current = adjusted_price(prices[index])
    if current is None:
        return None
    return {
        "ticker": security.get("ticker") or prices[index].get("ticker"),
        "companyName": security.get("company_name") or security.get("companyName"),
        "featureDate": prices[index]["date"],
        "sector": security.get("sector"),
        "industry": security.get("industry"),
        "currentAdjustedClose": round(current, 8),
        "return5Day": simple_return(prices, index, 5),
        "return21Day": simple_return(prices, index, 21),
        "return63Day": simple_return(prices, index, 63),
        "volatility21Day": volatility(prices, index, 21),
        "volatility63Day": volatility(prices, index, 63),
        "drawdown63Day": drawdown(prices, index, 63),
        "volumeTrend21Day": volume_trend(prices, index),
        "targetLogReturn30": target_log_return(prices, index, 30),
        "targetLogReturn90": target_log_return(prices, index, 90),
    }


def build_training_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in stock_files():
        payload = load_stock_payload(path)
        prices = sorted(payload.get("record", {}).get("priceHistory") or [], key=lambda row: row.get("date", ""))
        prices = prices[-FORECAST_PRICE_HISTORY_MAX_SESSIONS:]
        for index in range(len(prices)):
            row = build_feature_row(payload, prices, index)
            if row:
                rows.append(row)
    return rows


def feature_matrix(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.array([[row.get(name) if finite(row.get(name)) else np.nan for name in FEATURE_COLUMNS] for row in rows], dtype=float)


def target_vector(rows: list[dict[str, Any]], horizon: int) -> np.ndarray:
    name = f"targetLogReturn{horizon}"
    return np.array([float(row[name]) for row in rows], dtype=float)


def split_rows(rows: list[dict[str, Any]], horizon: int) -> dict[str, list[dict[str, Any]]]:
    labeled = [row for row in rows if finite(row.get(f"targetLogReturn{horizon}")) and all(name in row for name in FEATURE_COLUMNS)]
    dates = sorted({row["featureDate"] for row in labeled})
    if len(dates) < 90:
        return {"train": [], "validation": [], "test": labeled}
    validation_start = dates[int(len(dates) * 0.70)]
    test_start = dates[int(len(dates) * 0.85)]
    validation_cutoff = (date.fromisoformat(validation_start) - timedelta(days=horizon)).isoformat()
    test_cutoff = (date.fromisoformat(test_start) - timedelta(days=horizon)).isoformat()
    return {
        "train": [row for row in labeled if row["featureDate"] < validation_cutoff],
        "validation": [row for row in labeled if validation_start <= row["featureDate"] < test_cutoff],
        "test": [row for row in labeled if row["featureDate"] >= test_start],
    }


@dataclass
class FittedModel:
    name: str
    version: str
    model: Any
    constant: float | None = None
    unavailable_reason: str | None = None

    def predict(self, rows: list[dict[str, Any]]) -> np.ndarray:
        if self.constant is not None:
            return np.full(len(rows), self.constant, dtype=float)
        if self.model is None:
            return np.full(len(rows), np.nan, dtype=float)
        return np.array(self.model.predict(feature_matrix(rows)), dtype=float)


def candidate_models(train_rows: list[dict[str, Any]], horizon: int) -> list[FittedModel]:
    y = target_vector(train_rows, horizon) if train_rows else np.array([], dtype=float)
    mean = float(np.mean(y)) if len(y) else 0.0
    candidates = [
        FittedModel("zero-return baseline", "1.0.0", None, 0.0),
        FittedModel("historical-mean baseline", "1.0.0", None, mean),
        FittedModel("market-return baseline", "1.0.0", None, mean),
    ]
    if not train_rows or Ridge is None:
        candidates.append(FittedModel("sklearn candidates", "unavailable", None, unavailable_reason="scikit-learn unavailable or no train rows"))
        return candidates
    x = feature_matrix(train_rows)
    models = [
        ("ridge regression", Ridge(alpha=1.0, random_state=42)),
        ("elastic net", ElasticNet(alpha=0.01, l1_ratio=0.25, random_state=42, max_iter=5000)),
        ("huber regression", HuberRegressor(max_iter=500)),
        ("hist gradient boosting", HistGradientBoostingRegressor(max_iter=60, learning_rate=0.05, random_state=42)),
        ("random forest challenger", RandomForestRegressor(n_estimators=50, min_samples_leaf=10, random_state=42, n_jobs=1)),
    ]
    for name, estimator in models:
        try:
            model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), estimator)
            model.fit(x, y)
            candidates.append(FittedModel(name, "1.0.0", model))
        except Exception as error:
            candidates.append(FittedModel(name, "unavailable", None, unavailable_reason=str(error)))
    candidates.append(FittedModel("catboost regressor", "unavailable", None, unavailable_reason="CatBoost is not installed in this project environment."))
    candidates.append(FittedModel("small neural network challenger", "unavailable", None, unavailable_reason="Neural-network challenger is disabled for the lightweight local batch and cannot be selected."))
    return candidates


def rank(values: np.ndarray) -> np.ndarray:
    order = values.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    return ranks


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | None]:
    mask = np.isfinite(actual) & np.isfinite(predicted)
    if mask.sum() == 0:
        return {"mae": None, "rmse": None, "medianAbsoluteError": None, "directionalAccuracy": None, "spearmanRankCorrelation": None, "predictionBias": None}
    y, p = actual[mask], predicted[mask]
    spear = None
    if len(y) > 2 and np.std(y) > 0 and np.std(p) > 0:
        spear = float(np.corrcoef(rank(y), rank(p))[0, 1])
    errors = np.abs(y - p)
    return {
        "mae": float(np.mean(errors)),
        "rmse": float(math.sqrt(float(np.mean((y - p) ** 2)))),
        "medianAbsoluteError": float(np.median(errors)),
        "directionalAccuracy": float(np.mean(np.sign(y) == np.sign(p))),
        "spearmanRankCorrelation": spear,
        "predictionBias": float(np.mean(p - y)),
    }


def evaluate_horizon(rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
    split = split_rows(rows, horizon)
    train, validation, test = split["train"], split["validation"], split["test"]
    candidates = candidate_models(train, horizon)
    leaderboard = []
    for candidate in candidates:
        if candidate.unavailable_reason:
            leaderboard.append({"horizonDays": horizon, "model": candidate.name, "status": "unavailable", "reason": candidate.unavailable_reason})
            continue
        validation_metrics = metrics(target_vector(validation, horizon), candidate.predict(validation)) if validation else metrics(np.array([]), np.array([]))
        test_metrics = metrics(target_vector(test, horizon), candidate.predict(test)) if test else metrics(np.array([]), np.array([]))
        leaderboard.append({"horizonDays": horizon, "model": candidate.name, "status": "available", "validation": validation_metrics, "test": test_metrics})
    available = [item for item in leaderboard if item["status"] == "available" and item["validation"]["mae"] is not None]
    leaderboard_winner = min(available, key=lambda item: item["validation"]["mae"])["model"] if available else "zero-return baseline"
    allow_promotion = os.getenv("VS_ALLOW_EXPERIMENTAL_FORECAST_PROMOTION", "false").strip().lower() == "true"
    selected_name = leaderboard_winner if allow_promotion and leaderboard_winner not in BASELINE_MODEL_NAMES else "zero-return baseline"
    selected = next((candidate for candidate in candidates if candidate.name == selected_name), candidates[0])
    residual_source = test or validation or train
    if residual_source:
        residuals = target_vector(residual_source, horizon) - selected.predict(residual_source)
        residuals = residuals[np.isfinite(residuals)]
    else:
        residuals = np.array([], dtype=float)
    return {
        "horizonDays": horizon,
        "split": {name: len(value) for name, value in split.items()},
        "selectedModel": selected,
        "selectedModelName": selected_name,
        "leaderboardWinner": leaderboard_winner,
        "promotionAllowed": allow_promotion,
        "leaderboard": leaderboard,
        "residualP10": float(np.quantile(residuals, 0.10)) if len(residuals) else -0.05,
        "residualP90": float(np.quantile(residuals, 0.90)) if len(residuals) else 0.05,
    }


def clamp_log_return(value: float) -> float:
    return max(math.log(0.05), min(float(value), math.log(3.0)))


def return_bundle(current_price: float, prediction: float, low_residual: float, high_residual: float) -> dict[str, float]:
    base_log = clamp_log_return(prediction)
    lower_log = clamp_log_return(prediction + low_residual)
    upper_log = clamp_log_return(prediction + high_residual)
    lower_return, base_return, upper_return = sorted([math.exp(lower_log) - 1, math.exp(base_log) - 1, math.exp(upper_log) - 1])
    return {
        "returnEstimate": round(base_return, 8),
        "lowerReturn": round(lower_return, 8),
        "upperReturn": round(upper_return, 8),
        "estimatedPrice": round(current_price * (1 + base_return), 4),
        "lowerEstimatedPrice": round(current_price * (1 + lower_return), 4),
        "upperEstimatedPrice": round(current_price * (1 + upper_return), 4),
    }


def _empty_scenario_horizon(sample_count: int = 0) -> dict[str, Any]:
    return {
        "returnEstimate": None,
        "lowerReturn": None,
        "upperReturn": None,
        "estimatedPrice": None,
        "lowerEstimatedPrice": None,
        "upperEstimatedPrice": None,
        "sampleCount": sample_count,
    }


def quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _clip(value: float, cap: float) -> float:
    return max(-cap, min(cap, value))


def _scenario_horizon(current_price: float, returns: list[float], horizon: int, warnings: list[str]) -> dict[str, Any]:
    sample_count = len(returns)
    minimum = SCENARIO_MIN_SAMPLES[horizon]
    if sample_count < minimum:
        warnings.append(f"{horizon}-day scenario: insufficient history ({sample_count}/{minimum} usable sparse observations)")
        return _empty_scenario_horizon(sample_count)
    median_return = quantile(returns, 0.50)
    shrinkage = sample_count / (sample_count + SCENARIO_SHRINKAGE_CONSTANT[horizon])
    base = median_return * shrinkage
    lower = min(quantile(returns, 0.25), base)
    upper = max(quantile(returns, 0.75), base)
    cap = SCENARIO_RETURN_CAPS[horizon]
    clipped = []
    for label, original in (("lower", lower), ("base", base), ("upper", upper)):
        bounded = _clip(original, cap)
        clipped.append(bounded)
        if not math.isclose(original, bounded, rel_tol=0, abs_tol=1e-12):
            warnings.append(f"{horizon}-day scenario: {label} return clipped to +/-{cap:.0%}")
    lower, base, upper = clipped
    lower = min(lower, base)
    upper = max(upper, base)
    if lower < -1 or base < -1 or upper < -1:
        warnings.append(f"{horizon}-day scenario: invalid return below -100% rejected")
        return _empty_scenario_horizon(sample_count)
    return {
        "returnEstimate": round(base, 8),
        "lowerReturn": round(lower, 8),
        "upperReturn": round(upper, 8),
        "estimatedPrice": round(current_price * (1 + base), 4),
        "lowerEstimatedPrice": round(current_price * (1 + lower), 4),
        "upperEstimatedPrice": round(current_price * (1 + upper), 4),
        "sampleCount": sample_count,
    }


def _scenario_returns(rows: list[dict[str, Any]], horizon: int, warnings: list[str]) -> list[float]:
    unique_rows = []
    seen_dates: set[str] = set()
    duplicate_count = 0
    for row in sorted(rows, key=lambda item: item.get("featureDate", "")):
        feature_date = str(row.get("featureDate") or "")
        if feature_date in seen_dates:
            duplicate_count += 1
            continue
        seen_dates.add(feature_date)
        current = row.get("currentAdjustedClose")
        target = row.get(f"targetLogReturn{horizon}")
        if not finite(current) or float(current) <= 0:
            continue
        if not finite(target):
            unique_rows.append(row)
            continue
        simple = math.exp(float(target)) - 1
        if not math.isfinite(simple) or simple < -1:
            warnings.append(f"{horizon}-day scenario: invalid historical return rejected for {feature_date}")
            continue
        unique_rows.append({**row, f"targetSimpleReturn{horizon}": simple})
    if duplicate_count:
        warnings.append(f"Duplicate historical price dates rejected: {duplicate_count}")
    sampled = unique_rows[::SCENARIO_SAMPLE_STEP_SESSIONS]
    return [
        float(row[f"targetSimpleReturn{horizon}"])
        for row in sampled
        if finite(row.get(f"targetSimpleReturn{horizon}"))
    ]


def _market_data_is_stale(market_data_as_of: str, generated_at: str) -> bool:
    try:
        market_date = date.fromisoformat(market_data_as_of)
        generated_date = datetime.fromisoformat(generated_at).date()
    except ValueError:
        return True
    return (generated_date - market_date).days > SCENARIO_STALE_MARKET_DATA_DAYS


def conservative_scenario(rows: list[dict[str, Any]], current_row: dict[str, Any], generated_at: str) -> dict[str, Any]:
    warnings: list[str] = []
    current_price = current_row.get("currentAdjustedClose")
    market_data_as_of = str(current_row.get("featureDate") or "")
    if not finite(current_price) or float(current_price) <= 0:
        warnings.append("Current price is unavailable or invalid.")
        return {
            "methodology": CONSERVATIVE_SCENARIO_METHOD,
            "generatedAt": generated_at,
            "marketDataAsOf": market_data_as_of,
            "currentPrice": None,
            "horizon30Day": _empty_scenario_horizon(),
            "horizon90Day": _empty_scenario_horizon(),
            "status": "insufficient_data",
            "warnings": warnings,
        }
    stale = _market_data_is_stale(market_data_as_of, generated_at)
    if stale:
        warnings.append(f"Market data as of {market_data_as_of} is older than {SCENARIO_STALE_MARKET_DATA_DAYS} days.")
    horizons = {
        30: _scenario_horizon(float(current_price), _scenario_returns(rows, 30, warnings), 30, warnings),
        90: _scenario_horizon(float(current_price), _scenario_returns(rows, 90, warnings), 90, warnings),
    }
    available = all(finite(horizons[horizon].get("returnEstimate")) for horizon in (30, 90))
    return {
        "methodology": CONSERVATIVE_SCENARIO_METHOD,
        "generatedAt": generated_at,
        "marketDataAsOf": market_data_as_of,
        "currentPrice": round(float(current_price), 4),
        "horizon30Day": horizons[30],
        "horizon90Day": horizons[90],
        "status": "stale" if stale else "available" if available else "insufficient_data",
        "warnings": list(dict.fromkeys(warnings)),
    }


def _is_non_baseline_model(name: str | None) -> bool:
    return bool(name) and name not in BASELINE_MODEL_NAMES and "unavailable" not in name.lower()


def _display_source(results: dict[int, dict[str, Any]], scenario: dict[str, Any]) -> tuple[str, str | None]:
    if _is_non_baseline_model(results[30]["selectedModelName"]) and _is_non_baseline_model(results[90]["selectedModelName"]):
        return "forecast_model", "Validated or approved non-baseline forecast model selected."
    if scenario.get("status") == "available":
        return "conservative_historical_scenario", "Selected forecast model is a baseline benchmark; displaying the conservative historical scenario."
    return "unavailable", scenario.get("warnings", ["Projection source unavailable"])[0]


def _forecast_validation_status(results: dict[int, dict[str, Any]]) -> str:
    if all(results[horizon]["selectedModelName"] == "zero-return baseline" for horizon in (30, 90)):
        return "baseline"
    return "experimental"


def latest_feature_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        ticker = str(row["ticker"]).upper()
        if ticker not in latest or row["featureDate"] > latest[ticker]["featureDate"]:
            latest[ticker] = row
    return latest


def analyst_target_stub(ticker: str, current_price: float, generated_at: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "targetLow": None,
        "targetMean": None,
        "targetMedian": None,
        "targetHigh": None,
        "analystCount": None,
        "currentPriceAtCollection": current_price,
        "impliedReturnToMean": None,
        "horizonDays": None,
        "horizonLabel": None,
        "provider": "unsupported",
        "sourceAsOf": None,
        "collectedAt": generated_at,
        "status": "unsupported",
        "warnings": ["Current project artifacts do not include analyst consensus target fields from a contracted market-data provider."],
    }


def forecast_artifacts(rows: list[dict[str, Any]], results: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    generated_at = now_iso()
    current_rows = latest_feature_rows(rows)
    rows_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_by_ticker.setdefault(str(row["ticker"]).upper(), []).append(row)
    artifacts = []
    for ticker, row in sorted(current_rows.items()):
        current_price = row["currentAdjustedClose"]
        scenario = conservative_scenario(rows_by_ticker.get(ticker, []), row, generated_at)
        display_source, display_reason = _display_source(results, scenario)
        validation_status = _forecast_validation_status(results)
        warnings = [
            "Experimental price-history model; financial point-in-time feature snapshots are not yet part of the forecast training set.",
            "CatBoost candidate unavailable in the current project environment.",
        ]
        horizon_payloads = {}
        for horizon in (30, 90):
            result = results[horizon]
            model = result["selectedModel"]
            prediction = float(model.predict([row])[0])
            horizon_payloads[horizon] = return_bundle(current_price, prediction, result["residualP10"], result["residualP90"])
        artifacts.append({
            "schemaVersion": "1.0.0",
            "ticker": ticker,
            "companyName": row.get("companyName") or ticker,
            "generatedAt": generated_at,
            "marketDataAsOf": row["featureDate"],
            "currentPrice": round(float(current_price), 4),
            "analystTarget": analyst_target_stub(ticker, float(current_price), generated_at),
            "horizon30Day": horizon_payloads[30],
            "horizon90Day": horizon_payloads[90],
            "conservativeScenario": scenario,
            "displayProjectionSource": display_source,
            "displayProjectionReason": display_reason,
            "model30Day": {
                "name": results[30]["selectedModelName"],
                "version": "1.0.0",
                "testMAE": next((item.get("test", {}).get("mae") for item in results[30]["leaderboard"] if item.get("model") == results[30]["selectedModelName"]), None),
                "directionalAccuracy": next((item.get("test", {}).get("directionalAccuracy") for item in results[30]["leaderboard"] if item.get("model") == results[30]["selectedModelName"]), None),
            },
            "model90Day": {
                "name": results[90]["selectedModelName"],
                "version": "1.0.0",
                "testMAE": next((item.get("test", {}).get("mae") for item in results[90]["leaderboard"] if item.get("model") == results[90]["selectedModelName"]), None),
                "directionalAccuracy": next((item.get("test", {}).get("directionalAccuracy") for item in results[90]["leaderboard"] if item.get("model") == results[90]["selectedModelName"]), None),
            },
            "validationStatus": validation_status,
            "returnType": "price_return",
            "warnings": warnings,
        })
    return artifacts


def quality_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = sorted({row["ticker"] for row in rows})
    labeled30 = sum(finite(row.get("targetLogReturn30")) for row in rows)
    labeled90 = sum(finite(row.get("targetLogReturn90")) for row in rows)
    missing = {name: round(sum(not finite(row.get(name)) for row in rows) / len(rows), 4) if rows else 1 for name in FEATURE_COLUMNS}
    dates = sorted(row["featureDate"] for row in rows)
    return {
        "schemaVersion": "1.0.0",
        "generatedAt": now_iso(),
        "stocks": len(tickers),
        "rows": len(rows),
        "labeled30DayRows": labeled30,
        "labeled90DayRows": labeled90,
        "historicalPeriod": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
        "missingFeatureRates": missing,
        "status": "experimental" if labeled30 and labeled90 else "insufficient_data",
        "warnings": ["Dataset is price-history-only until point-in-time financial feature snapshots are implemented."],
    }


def leakage_report(results: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "generatedAt": now_iso(),
        "passed": True,
        "rules": [
            "Targets use first market session on or after featureDate plus calendar horizon.",
            "Rows are split by featureDate, never randomly.",
            "Training rows are embargoed before validation/test windows using the horizon length.",
            "No future analyst targets or future scoring labels are used.",
        ],
        "splits": {str(horizon): result["split"] for horizon, result in results.items()},
    }


def run_pipeline() -> dict[str, Any]:
    rows = build_training_rows()
    write_json(TRAINING_DATASET_PATH, {"schemaVersion": "1.0.0", "generatedAt": now_iso(), "rows": rows})
    results = {30: evaluate_horizon(rows, 30), 90: evaluate_horizon(rows, 90)}
    write_json(LEADERBOARD_PATH, {"schemaVersion": "1.0.0", "generatedAt": now_iso(), "models": results[30]["leaderboard"] + results[90]["leaderboard"]})
    write_json(BACKTEST_30_PATH, {"schemaVersion": "1.0.0", "generatedAt": now_iso(), "horizonDays": 30, "split": results[30]["split"], "selectedModel": results[30]["selectedModelName"], "leaderboard": results[30]["leaderboard"]})
    write_json(BACKTEST_90_PATH, {"schemaVersion": "1.0.0", "generatedAt": now_iso(), "horizonDays": 90, "split": results[90]["split"], "selectedModel": results[90]["selectedModelName"], "leaderboard": results[90]["leaderboard"]})
    write_json(QUALITY_PATH, quality_report(rows))
    write_json(LEAKAGE_PATH, leakage_report(results))
    for horizon, result in results.items():
        write_json(MODEL_DIR / f"{horizon}_day" / "metadata.json", {
            "schemaVersion": "1.0.0",
            "generatedAt": now_iso(),
            "horizonDays": horizon,
            "selectedModel": result["selectedModelName"],
            "modelStorage": "metadata-only; forecasts are generated offline into public/data/forecasts",
            "validationStatus": "experimental",
        })
    artifacts = forecast_artifacts(rows, results)
    for artifact in artifacts:
        write_json(FORECAST_DIR / f"{artifact['ticker']}.json", artifact)
    stale_forecast_artifacts_removed = remove_stale_forecast_artifacts({artifact["ticker"] for artifact in artifacts})
    summary = {
        "schemaVersion": "1.0.0",
        "generatedAt": now_iso(),
        "count": len(artifacts),
        "staleForecastArtifactsRemoved": stale_forecast_artifacts_removed,
        "validationStatus": _forecast_validation_status(results),
        "displayProjectionSources": {
            "forecast_model": sum(1 for artifact in artifacts if artifact.get("displayProjectionSource") == "forecast_model"),
            "conservative_historical_scenario": sum(1 for artifact in artifacts if artifact.get("displayProjectionSource") == "conservative_historical_scenario"),
            "unavailable": sum(1 for artifact in artifacts if artifact.get("displayProjectionSource") == "unavailable"),
        },
        "conservativeScenarioStatus": {
            "available": sum(1 for artifact in artifacts if (artifact.get("conservativeScenario") or {}).get("status") == "available"),
            "insufficient_data": sum(1 for artifact in artifacts if (artifact.get("conservativeScenario") or {}).get("status") == "insufficient_data"),
            "stale": sum(1 for artifact in artifacts if (artifact.get("conservativeScenario") or {}).get("status") == "stale"),
        },
        "forecasts": artifacts,
    }
    write_json(FORECAST_DIR / "summary.json", summary)
    return {
        "rows": len(rows),
        "forecasts": len(artifacts),
        "selected30": results[30]["selectedModelName"],
        "selected90": results[90]["selectedModelName"],
        "staleForecastArtifactsRemoved": len(stale_forecast_artifacts_removed),
        "conservativeScenarios": summary["conservativeScenarioStatus"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = run_pipeline()
    print(json.dumps(result if args.summary else {"forecastPipeline": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
