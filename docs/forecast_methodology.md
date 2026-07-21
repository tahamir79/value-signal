# ValueSignal Forecast and Conservative Scenario Methodology

**Status:** experimental research support
**Last updated:** 2026-07-21 UTC
**Primary code:** `scripts/forecast/pipeline.py`

This document explains how ValueSignal generates 30-day and 90-day forecast artifacts and how the separate conservative historical scenario is used for saved-stock projections.

## 1. What this layer is

The forecast layer is a research display layer. It helps users ask, "If I saved this position at the current documented price, what conservative 30/90-day scenario does ValueSignal show?"

It is not a trading recommendation, a guaranteed price target, or a validated prediction system.

## 2. Inputs

Forecast rows are built from generated stock detail artifacts:

- `public/data/stocks/{TICKER}.json`
- `record.priceHistory`

The pipeline uses price history only. It does not currently use point-in-time historical ValueSignal scores, analyst estimates, earnings forecasts, options data, macro data, or RAG output.

The current training window is capped by `FORECAST_PRICE_HISTORY_MAX_SESSIONS` so local and scheduled runs stay practical while still providing enough history for sparse scenario sampling.

## 3. Feature rows

For each price-history date, the pipeline derives:

- current adjusted close;
- 5-day return;
- 21-day return;
- 63-day return;
- 21-day volatility;
- 63-day volatility;
- 63-day drawdown;
- 21-day volume trend;
- future 30-calendar-day log return;
- future 90-calendar-day log return.

Price selection prefers adjusted close and falls back to close. Invalid or non-positive prices are rejected.

## 4. Target construction

For a feature date, the target return uses the first available trading session on or after:

- feature date + 30 calendar days;
- feature date + 90 calendar days.

The target is stored as a log return for model evaluation. Forecast artifacts expose simple returns for display.

Rows whose future outcome is not yet known are unlabeled and are not used for supervised target evaluation.

## 5. Model evaluation

Candidate models include:

- zero-return baseline;
- historical-mean baseline;
- market-return baseline;
- ridge regression;
- elastic net;
- huber regression;
- histogram gradient boosting;
- random forest challenger;
- unavailable placeholders for optional/disabled models.

Rows are split by feature date, not randomly. The split includes an embargo so training rows cannot leak into validation/test windows through future-return labels.

The leaderboard records validation/test metrics, but the selected production artifact model remains conservative.

## 6. Model promotion guard

Current official behavior:

```text
selected 30-day model = zero-return baseline
selected 90-day model = zero-return baseline
```

The pipeline may identify a non-baseline leaderboard winner, but it does not promote it unless:

```text
VS_ALLOW_EXPERIMENTAL_FORECAST_PROMOTION=true
```

Without that explicit environment gate, both horizons stay on the zero-return baseline. This preserves auditability and prevents the website from implying a validated predictive model where none has been approved.

## 7. Conservative historical scenario

Because the selected forecast model is currently a baseline, the saved-stock UI can display a separate scenario:

```text
ValueSignal Conservative Historical Scenario v1
```

Artifact method:

```text
valuesignal_conservative_historical_scenario_v1
```

This scenario is not the selected forecast model.

### Method

For each ticker and horizon:

1. Sort price observations chronologically.
2. Use adjusted close when available.
3. Deduplicate dates.
4. Sample approximately every 21 sessions.
5. Use only observations with known future outcomes.
6. Compute historical simple returns.
7. Reject invalid returns below -100%.
8. Require minimum sparse sample coverage:
   - 30-day: 24 samples;
   - 90-day: 12 samples.
9. Use the historical median return as the center.
10. Shrink the median toward zero:

```text
shrinkageFactor = sampleCount / (sampleCount + shrinkageConstant)
baseReturn = historicalMedianReturn * shrinkageFactor
```

Initial shrinkage constants:

- 30-day: 24;
- 90-day: 18.

11. Use empirical 25th and 75th percentiles for lower/upper range.
12. Enforce lower <= base <= upper.
13. Clip all scenario returns:
   - 30-day: between -8% and +8%;
   - 90-day: between -15% and +15%.
14. Mark scenario stale if market data is older than 10 days.

The scenario never boosts estimates because a stock is "potentially undervalued." Today's score is not treated as a historical point-in-time score.

## 8. Output fields

Each forecast artifact contains:

- selected model metadata;
- model 30/90 horizon returns and estimated prices;
- analyst target object, currently unsupported;
- conservative scenario object;
- `displayProjectionSource`;
- `displayProjectionReason`;
- validation status.

Projection source priority:

1. `forecast_model` for approved non-baseline models;
2. `conservative_historical_scenario` for valid scenario fallback;
3. `unavailable` with a specific reason.

## 9. Current generated state

Current generated artifact state:

- forecasts: 245;
- selected 30-day model: zero-return baseline;
- selected 90-day model: zero-return baseline;
- conservative scenarios available: 203;
- insufficient-history scenarios: 42;
- stale scenarios: 0.

Example AAPL:

- market data as of: 2026-07-20;
- current price: 326.59;
- 30-day return estimate: 1.999019%;
- 30-day estimated price: 333.1186;
- 30-day sample count: 25;
- 90-day return estimate: 3.757468%;
- 90-day estimated price: 338.8615;
- 90-day sample count: 23.

## 10. Validation

Core commands:

```powershell
python scripts/forecast/run_forecast_pipeline.py --summary
python scripts/forecast/audit_training_dataset.py
python scripts/forecast/evaluate_models.py
python scripts/forecast/audit_forecasts.py
python -m unittest tests.test_forecast_pipeline -v
```

Audit expectations:

- lower/base/upper returns are ordered;
- simple returns remain above -100%;
- zero returns are treated as available values;
- stale/unavailable states are explicit;
- analyst targets remain unsupported until a real provider exists;
- forecast count matches the current active stock artifact count after cleanup.

## 11. Disclosure language

User-facing conservative scenario disclosure:

> ValueSignal's conservative historical scenario is based on the stock's prior price behavior and is not a validated prediction, guarantee, or investment recommendation. Future market outcomes may differ materially.
