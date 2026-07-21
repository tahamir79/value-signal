# ValueSignal Artifact Schema Notes

**Last updated:** 2026-07-21 UTC
**Purpose:** compact schema map for generated artifacts used by the frontend, audits, and companion planning models.

Generated JSON artifacts are reproducible outputs from scripts. Do not hand-maintain them.

## 1. Core frontend artifacts

| Path | Producer | Consumer | Notes |
|---|---|---|---|
| `public/data/dashboard.json` | `scripts/run_etl.py` | dashboard | active rows for successful ETL tickers |
| `public/data/stocks/summary.json` | `scripts/run_etl.py` | dashboard, forecast roster | current active stock roster |
| `public/data/stocks/{TICKER}.json` | `scripts/run_etl.py` | stock detail, forecast pipeline | includes price history, facts, balance-sheet context |
| `public/data/features.json` | `scripts/run_etl.py` | audits, methodology | normalized feature rows |
| `public/data/signals.json` | `scripts/run_etl.py` | dashboard, stock detail, RAG context | deterministic official signal and scores |
| `public/data/etl_report.json` | `scripts/run_etl.py` | health/reporting | per-ticker failures and counts |
| `public/data/universe_coverage_report.json` | `scripts/run_etl.py` and search backfill | health, methodology | coverage counts and BM25/balance status |
| `public/data/backtest_results.json` | `scripts/run_etl.py` / `scripts/backtest.py` | backtest page | scaled run may be intentionally unavailable |
| `public/data/search_index.json` | `scripts/build_search_index.py` | search route | per-ticker BM25 manifest |
| `public/data/search/{TICKER}.json` | `scripts/build_search_index.py` | search route, local RAG | ticker-specific BM25 corpus |
| `public/data/pipeline_health.json` | `scripts/pipeline_health.py` | future frontend/status | compact safe health summary |

The `growthSpurt` object is produced by `scripts/run_etl.py` during a normal ETL run. `scripts/build_growth_spurt_artifacts.py` can repopulate only the Growth Spurt fields from existing generated stock price histories when a full provider refresh is unnecessary.

## 2. Forecast artifacts

Summary:

```text
public/data/forecasts/summary.json
```

Ticker detail:

```text
public/data/forecasts/{TICKER}.json
```

Important fields:

- `ticker`
- `companyName`
- `generatedAt`
- `marketDataAsOf`
- `currentPrice`
- `analystTarget`
- `horizon30Day`
- `horizon90Day`
- `conservativeScenario`
- `displayProjectionSource`
- `displayProjectionReason`
- `model30Day`
- `model90Day`
- `validationStatus`
- `returnType`
- `warnings`

Allowed `displayProjectionSource`:

```text
forecast_model
conservative_historical_scenario
unavailable
```

Allowed validation status:

```text
baseline
experimental
validated
insufficient_data
stale
```

Current selected models:

```text
zero-return baseline
```

This baseline is a valid auditable model result, not an unavailable value.

## 3. Conservative scenario object

Method:

```text
valuesignal_conservative_historical_scenario_v1
```

Status:

```text
available
insufficient_data
stale
```

Each horizon includes:

- `returnEstimate`
- `lowerReturn`
- `upperReturn`
- `estimatedPrice`
- `lowerEstimatedPrice`
- `upperEstimatedPrice`
- `sampleCount`
- `status`
- `usableObservationCount`
- `requiredObservationCount`
- `unavailableReason`

Null return/price fields mean the scenario is unavailable for that horizon. Do not substitute zero unless the artifact explicitly stores zero.

`unavailableReason` is horizon-specific. The frontend should render a compact display reason such as `Not enough historical data` plus `usableObservationCount of requiredObservationCount required observations`; it should not reuse a 30-day reason on a 90-day card.

## 4. Growth Spurt artifact

Embedded paths:

```text
public/data/dashboard.json records[].growthSpurt
public/data/stocks/summary.json records[].growthSpurt
public/data/stocks/{TICKER}.json record.growthSpurt
```

Benchmark report:

```text
data/reports/growth_spurt_benchmark.json
```

Allowed `status` values:

```text
detected
emerging
not_detected
unavailable
```

Core fields:

- `ticker`
- `generatedAt`
- `marketDataAsOf`
- `growthSpurtScore`
- `primaryWindowSessions`
- `confirmationWindowSessions`
- `metrics`
- `scoreBreakdown`
- `benchmarkPercentile`
- `metricPercentiles`
- `reasonCodes`
- `warnings`

`analystTarget` is a normalized provider placeholder until a legitimate market-data provider is configured:

```text
targetLow
targetMean
targetMedian
targetHigh
analystCount
currentPriceAtCollection
targetHorizonDays / horizonDays
targetHorizonLabel / horizonLabel
provider
sourceAsOf
collectedAt
status
warnings
```

Allowed analyst/market target status:

```text
available
stale
horizon_unknown
insufficient_data
unsupported
```

Do not fabricate analyst targets and do not populate these fields from ValueSignal scenarios. `src/lib/position-projections.ts` derives customer-facing `HoldingOutcome` records from forecast artifacts at render time.

Important distinction: `unavailable` means insufficient usable stock or SPY benchmark history. It is not a zero score.

## 5. Pipeline health artifacts

Full internal report:

```text
data/reports/pipeline_health_report.json
```

Public safe report:

```text
public/data/pipeline_health.json
```

Top-level fields:

- `schemaVersion`
- `generatedAt`
- `overallStatus`
- `releaseReadiness`
- `criticalFailures`
- `nonCriticalFailures`
- `expectedUnavailable`
- `dataQualityWarnings`
- `warnings`
- `stages`
- `failedTickers`

Stage statuses:

```text
success
partial_success
failed
skipped
unavailable_expected
```

The public report excludes artifact paths, raw traces, local paths, and secrets.

Current release-readiness values:

```text
ready
ready_with_known_limitations
blocked
```

The current fixture should read as `ready_with_known_limitations`: all core artifacts are present, but the report still exposes true noncritical ETL ticker failures, expected unavailable market targets/backtest, skipped insufficient forecast-history cases, and balance-sheet coverage warnings.

## 6. Stale artifact cleanup

`scripts/run_etl.py` removes stale stock detail files that are not in the successful active ETL roster.

`scripts/forecast/pipeline.py` reads `public/data/stocks/summary.json` as the active forecast roster and removes stale forecast files after generation.

This prevents old ticker files from lingering after a partial provider run.

## 7. Commit/deploy caution

Generated artifacts can be large. Before commit:

- inspect `git status --short`;
- exclude `logs/`, `phases/`, local caches, and secrets;
- confirm generated stock and forecast counts match expected active roster;
- run audits and build.
