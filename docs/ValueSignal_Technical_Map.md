# ValueSignal Technical Map

**Purpose:** durable engineering/finance handoff for the companion ChatGPT and future Codex sessions.
**Companion atlas:** `docs/ValueSignal_Project_Blueprint.md`
**Last updated:** 2026-07-22 UTC
**Repo path:** `C:\Users\stahm\Projects\Decision Scientist`
**Branch:** `scale-universe-foundation`
**Checkpoint commit before this projection/health work:** `6043820 checkpoint: before historical scenario and pipeline health cleanup`
**Current state:** full-universe local artifacts are generated and validated; commit/deploy is pending a final packaging decision because the public JSON payload is now much larger than the previous 245-stock fixture.

Treat code, tests, workflow YAML, and generated artifacts as the source of truth if this map drifts. Treat `public/data/*.json` as generated artifacts, not manually maintained data.

---

## 1. Product boundary

ValueSignal is a cautious public-company research system. It classifies companies into transparent research signals, shows the evidence and missing data behind those signals, and lets a signed-in user save stocks/positions for research tracking.

It is not a trading bot. It must not issue buy/sell/hold advice, guarantee price movement, fabricate analyst targets, or let an LLM overwrite the deterministic signal.

Current product layers:

```text
Universe selection
  -> price + SEC companyfacts ETL
  -> feature engineering
  -> deterministic scoring and balance-sheet gates
  -> generated JSON artifacts
  -> dashboard / stock detail / methodology / saved stocks

SEC filings
  -> filing download + cleaning
  -> section-aware chunks
  -> BM25 per-ticker index
  -> evidence search and local-only RAG context

Stock price history
  -> experimental forecast model evaluation
  -> conservative historical scenario
  -> saved-stock 30/90-day position projections
  -> display-only Growth Spurt detector + SPY-relative benchmark
```

---

## 2. Current generated data snapshot

Current cleaned artifact counts after the checkpointed full-universe merge:

- Supported universe in `data/universe/universe_manifest.json`: **6,017** operating-company rows.
- Raw checkpoint fetches completed: **6,017 attempted**, **5,802 raw successes**, **215 raw failures**.
- Active stock records in `public/data/stocks/summary.json`: **5,799**
- Stock detail files in `public/data/stocks/{TICKER}.json`: **5,799**
- Forecast records in `public/data/forecasts/summary.json`: **5,799**
- Forecast detail files in `public/data/forecasts/{TICKER}.json`: **5,799**
- Conservative scaled-fast scenarios available: **5,475**
- Conservative scaled-fast scenarios insufficient history: **321**
- Stale scenario count: **3**
- Selected 30-day model: **zero-return baseline**
- Selected 90-day model: **zero-return baseline**
- Growth Spurt detector: generated from the merged ETL artifact; rerun `python scripts/benchmark_growth_spurt.py` for a fresh benchmark if the detector itself changes.
- Search index coverage: **199 indexed tickers** in per-ticker BM25 mode
- Pipeline health: **partial_success**, release readiness **ready_with_known_limitations**, with **0 critical failures** and **218 noncritical ETL failures**
- Local raw checkpoint store: about **26.2 GB** under ignored `data/checkpoints/etl_raw/`.
- `public/data/dashboard.json` is a dashboard-summary artifact, not the full per-ticker detail store. It omits repeated heavy blocks such as `balanceSheetScoringShadow`; full detail remains under `public/data/stocks/{TICKER}.json`, and scoring components remain in `public/data/signals.json`.
- Per-ticker artifact filenames are normalized through `scripts/artifact_paths.py` and `src/lib/artifact-paths.ts`. Windows-reserved ticker names keep their official ticker in JSON/URLs but receive a prefixed filename, e.g. ticker `CON` is stored at `public/data/stocks/_CON.json` and `public/data/forecasts/_CON.json`.

Current true partial causes:

- ETL provider failures for 218 symbols across price/facts fetches. These are noncritical because ticker failures are isolated and all successful tickers still publish.
- Balance-sheet coverage is partial for many companies because SEC companyfacts does not always expose every target balance-sheet field.

Expected unavailable states:

- Scaled scheduled ETL intentionally skips full backtest generation.
- 321 stocks do not have enough sparse historical observations for the conservative 30/90-day scenario.
- 3 forecast records are stale relative to the current scaled-fast run.
- Analyst/market target provider is not configured, so analyst target fields remain null/unsupported.
- Local Ollama/RAG is not a production dependency.
- BM25 filing evidence remains capped at 199 indexed tickers and should be scaled separately from market/companyfacts ETL.

---

## 3. Public preview and auth gate

The app keeps the original 10-stock universe public and gates the broader universe behind Google sign-in.

Public preview tickers:

```text
AAPL, MSFT, GOOGL, AMZN, JPM, JNJ, XOM, F, KO, INTC
```

Auth/gating mechanics:

- `src/lib/public-universe.ts` defines the preview set.
- `src/app/dashboard/page.tsx` reads auth state and generated artifacts.
- `src/features/dashboard/StockTable.tsx` shows the preview table and the lock/fade sign-in panel.
- `src/app/stock/[ticker]/page.tsx` blocks non-preview ticker pages when signed out.
- `src/components/AuthStatus.tsx` and `src/components/GoogleSignInButton.tsx` handle sign-in UI.

Auth prepares future protected AI/RAG features but does not change the scoring engine.

---

## 4. Official feature mechanics

Feature generation lives in:

- `scripts/features.py`
- `docs/feature_dictionary.md`

The scoring engine uses 10 primary features:

| Feature | Meaning | Direction |
|---|---|---|
| `return_30d` | recent 30-day price return | higher supports momentum |
| `return_90d` | recent 90-day price return | higher supports momentum |
| `annualized_volatility` | annualized daily return volatility | higher is riskier |
| `max_drawdown_1y` | worst 1-year drawdown | more negative is riskier |
| `earnings_yield` | earnings relative to market value | higher supports value |
| `sales_yield` | revenue relative to market value | higher supports value |
| `liabilities_to_assets` | liabilities as a share of assets | higher is balance-sheet risk |
| `revenue_growth` | revenue growth | higher supports quality |
| `net_margin` | profitability margin | higher supports quality |
| `net_margin_trend` | margin trend | higher supports quality |

Important mechanics:

- Prices prefer adjusted close when available.
- Fundamentals come from normalized SEC companyfacts.
- Missing values remain `null`; they are not converted to zero.
- Outliers are winsorized for percentile scoring and tracked as range warnings.
- Percentiles are computed inside the active universe batch.
- Missing evidence reduces confidence separately from the score values.

Display/context fields now include latest revenue, revenue growth, gross profit/gross margin when available, net margin, liabilities/assets, price, daily change, and market cap.

---

## 5. Component scores and signal classification

Scoring lives in:

- `scripts/scoring.py`
- `docs/scoring_specification.md`
- `src/lib/scoreExplanations.ts`

Component conventions:

| Component | Inputs | Direction |
|---|---|---|
| Value | earnings yield 60%, sales yield 40% | higher is better |
| Quality | net margin 45%, revenue growth 30%, net margin trend 25% | higher is better |
| Momentum | 90-day return 60%, 30-day return 40% | higher is better |
| Market risk | max drawdown 55%, volatility 45% | higher is worse |
| Balance-sheet risk | liabilities/assets plus official balance-sheet risk blend | higher is worse |
| Momentum risk | `100 - momentum` | higher is worse |

Each score stays in the 0-100 range. Contribution rows show feature, raw percentile, directed percentile, normalized weight, and contribution.

Confidence is feature availability, not prediction certainty:

| Available features | Confidence |
|---:|---|
| 9-10 | High |
| 7-8 | Medium |
| 5-6 | Low |
| fewer than 5 | Insufficient |

Official signal priority:

1. `insufficient-evidence`
2. `value-trap-risk`
3. `momentum-risk`
4. `potentially-undervalued`
5. `quality-watchlist`
6. `neutral`

Risk labels intentionally take priority over attractive value/quality labels. A low valuation with severe balance-sheet weakness should route toward risk language rather than promotional undervaluation language.

---

## 6. Balance-sheet-aware scoring

Balance-sheet work lives in:

- `scripts/balance_sheet.py`
- `docs/balance_sheet_scoring.md`
- `src/components/BalanceSheetHealth.tsx`

Current scheduled/default scoring mode is intended to be:

```text
BALANCE_SHEET_SCORING_MODE=official
```

Standalone artifacts remain intact:

- `data/fundamentals/balance_sheets/{TICKER}.json`
- `data/fundamentals/balance_sheets/manifest.json`
- related reports under `data/reports/`

Balance-sheet outputs:

- `liquidityScore`
- `leverageScore`
- `solvencyScore`
- `assetQualityScore`
- `balanceSheetQualityScore` where higher is better
- `balanceSheetRiskPenalty` where higher is worse
- triggered risk gates
- missing fields and extraction warnings

Official scoring blend:

- `scores.balanceSheetRisk` blends the prior liabilities/assets risk with `balanceSheetRiskPenalty`.
- `scores.quality` lightly blends in `balanceSheetQualityScore`.
- `balanceSheetScoringShadow` is preserved.
- `balanceSheetOfficialChange` records what changed and why.

Do not change official balance-sheet weights without running scoring comparison against the scoring-v1 checkpoint/baseline.

---

## 7. Forecast model vs conservative scenario

Forecast code lives in:

- `scripts/forecast/pipeline.py`
- `scripts/forecast/run_forecast_pipeline.py`
- `scripts/forecast/audit_training_dataset.py`
- `scripts/forecast/evaluate_models.py`
- `scripts/forecast/audit_forecasts.py`
- `tests/test_forecast_pipeline.py`

Frontend projection code lives in:

- `src/types/forecast.ts`
- `src/lib/position-projections.ts`
- `src/components/SavedStocksConsole.tsx`

Generated forecast artifacts:

- `public/data/forecasts/summary.json`
- `public/data/forecasts/{TICKER}.json`
- `models/forecast/30_day/metadata.json`
- `models/forecast/90_day/metadata.json`
- compact reports in `data/reports/forecast_*.json`

### 7.1 Current forecast truth

The current selected 30-day and 90-day models are both `zero-return baseline`.

That means:

- base model return is exactly `0.0`;
- model output is auditable and preserved;
- lower/upper model ranges come from residual quantiles;
- no challenger model is promoted by default.

`scripts/forecast/pipeline.py` evaluates challengers but only promotes a non-baseline when `VS_ALLOW_EXPERIMENTAL_FORECAST_PROMOTION=true`. Without that explicit environment gate, the selected model stays baseline.

### 7.2 Conservative historical scenario

The user-facing saved-position projection now uses a separate deterministic fallback:

```text
ValueSignal Conservative Historical Scenario v1
```

Artifact method string:

```text
valuesignal_conservative_historical_scenario_v1
```

Projection-source priority:

1. approved non-baseline forecast model;
2. conservative historical scenario;
3. unavailable with precise reason.

Scenario method:

- uses each stock's own generated price history;
- sorts observations chronologically;
- samples approximately every 21 sessions to avoid daily-overlap overconfidence;
- uses the first market session on or after 30/90 calendar days;
- computes simple returns;
- requires at least 24 sparse samples for 30-day and 12 sparse samples for 90-day;
- centers on the historical median return, shrunk toward zero;
- uses empirical 25th/75th percentile range;
- caps returns at +/-8% for 30-day and +/-15% for 90-day;
- marks stale data when market data is older than 10 days;
- does not adjust upward because a stock is labeled undervalued.

The scenario is not a trained model, not a forecast promotion, and not advice.

Example current AAPL scenario:

| Field | Value |
|---|---:|
| Current price | 326.59 |
| Market data as of | 2026-07-20 |
| 30-day return estimate | 1.999019% |
| 30-day range | -4.208451% to 7.560280% |
| 30-day estimated price | 333.1186 |
| 30-day sparse samples | 25 |
| 90-day return estimate | 3.757468% |
| 90-day range | -5.457619% to 13.215285% |
| 90-day estimated price | 338.8615 |
| 90-day sparse samples | 23 |

User-facing disclosure:

> ValueSignal's conservative historical scenario is based on the stock's prior price behavior and is not a validated prediction, guarantee, or investment recommendation. Future market outcomes may differ materially.

---

## 8. Saved-stock projection mechanics

Saved-stock UI and projection math live in:

- `src/components/SavedStocksConsole.tsx`
- `src/components/HoldingOutcomeCard.tsx`
- `src/lib/position-projections.ts`
- `src/types/forecast.ts`

The projection layer distinguishes four concepts:

1. selected ValueSignal forecast model;
2. conservative historical scenario;
3. user's personal scenario inputs;
4. analyst/market target object.

Personal 30/90 scenario fields are user-entered and do not change ValueSignal estimates.

Saved-position holding math:

```text
estimatedGainLossPerShare = estimatedSellPrice - currentPurchasePrice
estimatedTotalGainLoss = sharesHeld * estimatedGainLossPerShare
estimatedPositionValue = sharesHeld * estimatedSellPrice
```

For dollar-allocation mode, the projection layer first calculates implied shares:

```text
impliedShares = dollarAllocation / currentPrice
```

Then it uses the same per-share formula. Do not calculate `shares * returnEstimate`, and do not multiply a dollar allocation by an estimated sell price.

Current UI cards show a compact two-card ValueSignal grid:

- `ValueSignal 30 Days`;
- `ValueSignal 90 Days`.

At the top of each saved position, the UI shows position type, current price, current position value, allocation when dollar-based, `Implied shares` for dollar allocations, `Shares held` for share positions, and market data as-of date. Each ValueSignal outcome card makes estimated total gain/loss the largest number and does not repeat it as a row. Available cards then show gain/loss per share, estimated sell price, estimated position value, estimated return, scenario range, and projection source. Unavailable cards show only `Unavailable`, a concise reason, a horizon-specific observation detail when available, and a meaningful as-of date. The component receives normalized `HoldingOutcome` records from `src/lib/position-projections.ts`; React does not reproduce forecast-source selection or target time-scaling logic.

Internal fields now live inside a collapsed `Forecast methodology` panel:

- zero-return baseline status;
- selected model names;
- displayed projection source and sample count;
- optional user-entered personal 30/90-day scenarios.

Market-target scenarios stay hidden from the primary saved-portfolio UI until a legitimate provider supplies a consensus target plus documented horizon. Backend `marketTargetOutcomes` and `AnalystTargetArtifact` records remain for future compatibility. Unavailable market-target outcomes keep scenario source fields null. If a future provider gives a valid horizon, the implied 30/90-day scenario is time-scaled as `(1 + targetReturn)^(horizon / targetHorizonDays) - 1`; it is labeled as an assumption-based scenario, not an analyst-issued short-term forecast.

The saved-stock layout overflow was caused by nested grid children using fixed minimum widths and form controls lacking shrink/width constraints. The fix added `min-width: 0`, `box-sizing: border-box`, `width: 100%`, `max-width: 100%`, and safer `minmax(0, ...)` grid definitions in `src/app/globals.css`.

---

## 8.5 Growth Spurt detector

Growth Spurt code lives in:

- `scripts/growth_spurt.py`
- `scripts/build_growth_spurt_artifacts.py`
- `scripts/benchmark_growth_spurt.py`
- `src/components/GrowthSpurtBadge.tsx`
- `tests/test_growth_spurt.py`
- `tests/growthSpurtBadge.test.tsx`

Current mode:

```text
GROWTH_SPURT_MODE=display
```

Supported modes are `off`, `shadow`, `display`, and `official`. `official` is reserved and currently does not influence the official signal.

Formula mechanics:

- Uses adjusted close when available, otherwise close.
- Normalizes and sorts prices by date, deduping same-date rows.
- Requires at least 50 usable observations and uses a 63-session primary window with 21-session confirmation.
- Fits a Theil-Sen trend to log prices for robust 63-session and 21-session slope.
- Scores direction, consistency, SPY-relative strength, drawdown control, and recent confirmation/acceleration into `growthSpurtScore`.
- Rejects spike-dominated moves using `largestOneDayContribution63d` and `ONE_DAY_SPIKE_DOMINATED`.
- Computes cross-sectional percentiles for trend slope, R2, SPY excess return, drawdown-control score, and total Growth Spurt Score.

Detection threshold:

```text
detected if:
  score >= 70
  trendSlope63d > 0
  return63d > 0
  return21d >= 0
  trendFitR2_63d >= 0.45
  positiveWeekRatio63d >= 0.60
  maxDrawdown63d >= -0.15
  no ONE_DAY_SPIKE_DOMINATED warning

emerging if:
  score >= 55
  trendSlope63d > 0
  return63d > 0
  no spike dominance
```

Generated artifact locations:

- `public/data/dashboard.json` has dashboard-row `growthSpurt`.
- `public/data/stocks/summary.json` has compact summary `growthSpurt`.
- `public/data/stocks/{TICKER}.json` has full `growthSpurt` metrics.
- `data/reports/growth_spurt_benchmark.json` has point-in-time benchmark results.
- `public/data/etl_report.json`, `public/data/universe_coverage_report.json`, and `public/data/pipeline_health.json` include detector coverage counts.

User-facing boundary:

> This tag describes recent historical price behavior. It does not predict that the price will continue rising.

---

## 9. SEC filing retrieval and BM25

Retrieval code lives in:

- `scripts/build_search_index.py`
- `scripts/chunk_filings.py`
- `scripts/text_cleaning.py`
- `scripts/retrieval.py`
- `scripts/audit_search.py`
- `src/lib/search.ts`
- `src/app/api/search/route.ts`
- `src/components/FilingEvidencePanel.tsx`

Current search schema:

```text
3.0.0
```

Current production-safe behavior:

- BM25 remains the retrieval baseline.
- `public/data/search_index.json` is a manifest in per-ticker mode.
- Per-ticker indexes live under `public/data/search/{TICKER}.json`.
- Query expansion broadens common user terms like risk, supply chain, liquidity, revenue, margin, competition, and cybersecurity.
- BM25 status flags in dashboard/stock artifacts are updated from the manifest.

If a search says "No matching passage found," check:

1. whether the ticker is indexed;
2. whether the query maps to available filing language;
3. whether the ticker has recent 10-K/10-Q filings;
4. whether per-ticker search files exist.

Do not blame LLM/RAG for BM25 index coverage gaps.

---

## 10. Local RAG boundary

RAG code exists but is local/experimental:

- `rag/`
- `scripts/run_rag.py`
- `scripts/build_rag_embeddings.py`
- `src/app/api/rag/route.ts`
- `src/app/rag/page.tsx`
- `src/components/LocalRagConsole.tsx`
- `docs/rag_specification.md`

Production should show a safe placeholder unless local RAG is explicitly enabled. Local RAG may explain whether retrieved SEC evidence supports, weakens, complicates, or is insufficient for the official deterministic signal. It must not relabel the stock.

Allowed evidence-assessment values:

- Supports signal
- Weakens signal
- Mixed evidence
- Insufficient evidence
- Review recommended

---

## 11. Pipeline health model

Health code lives in:

- `scripts/pipeline_health.py`
- `tests/test_pipeline_health.py`

Generated health artifacts:

- `data/reports/pipeline_health_report.json`
- `public/data/pipeline_health.json`

Health statuses:

- `success`: core artifacts exist and no noncritical ticker/subsystem failure is present.
- `partial_success`: core artifacts exist, but one or more noncritical per-ticker/subsystem failures occurred.
- `failed`: a required core artifact is missing or a critical stage fails.
- `unavailable_expected`: subsystem intentionally unsupported/skipped, such as analyst targets or scaled backtest.

Top-level fixture fields:

- `overallStatus`: pipeline status using the strict success/partial/failed vocabulary.
- `releaseReadiness`: deployment-testing status; current value is `ready_with_known_limitations`.
- `criticalFailures`: failures that should block deployment/testing.
- `nonCriticalFailures`: true ticker/subsystem failures that do not block the generated website.
- `expectedUnavailable`: intentionally unavailable items, such as scaled backtest and analyst targets.
- `dataQualityWarnings`: coverage warnings, currently dominated by partial balance-sheet fields.

Current health summary:

- core artifacts: success;
- ETL ticker pipeline: partial success, 5 provider 404 failures;
- backtest: unavailable expected due scaled `--skip-backtest`;
- forecast artifacts: success with 42 skipped insufficient-history scenario cases;
- filing search index: success, 199 tickers;
- balance-sheet context: partial success, 199 usable/partial and 46 unavailable;
- growth-spurt detector: success with 245 attempted, 236 available states, 9 expected unavailable, 0 calculation failures;
- market targets: unavailable expected because no analyst target provider is configured.
- release readiness: ready with known limitations;
- expected unavailable count: 246;
- data-quality warnings: 226, currently from partial balance-sheet context rather than expected forecast/market-target gaps.

The public summary excludes local artifact paths and secrets.

---

## 12. Scheduled refresh workflow

Workflow:

- `.github/workflows/refresh-data.yml`

Current intended sequence:

1. checkout;
2. setup Python/Node;
3. run tests;
4. build scaled universe;
5. run ETL with `--skip-backtest`, including Growth Spurt artifacts when mode is `display`;
6. benchmark the Growth Spurt detector against SPY point-in-time snapshots;
7. rebuild BM25 search index;
8. run forecast pipeline;
9. run feature/scoring/backtest/search/forecast audits;
10. generate pipeline health;
11. commit generated artifacts if changed;
12. push to trigger Vercel redeployment.

Important environment/secret requirements:

- `VS_CONTACT_EMAIL` in GitHub secrets for SEC `VS_USER_AGENT`.
- Vercel auth/database variables are configured outside Git.
- No real secret values should appear in repo docs, artifacts, or logs.

Workflow gotcha already fixed:

- `data/universe/universe.json` must be created before `scripts/run_etl.py --universe data/universe/universe.json`.

---

## 13. Commands

Run from repo root.

Local app:

```powershell
npm run dev
npm run typecheck
npm run build
```

Tests:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
npm run test:brief
```

Core audits:

```powershell
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/audit_backtest.py
python scripts/audit_search.py
python scripts/build_growth_spurt_artifacts.py
python scripts/benchmark_growth_spurt.py
```

Forecast:

```powershell
python scripts/forecast/run_forecast_pipeline.py --summary
python scripts/forecast/audit_training_dataset.py
python scripts/forecast/evaluate_models.py
python scripts/forecast/audit_forecasts.py
```

Pipeline health:

```powershell
python scripts/pipeline_health.py
```

Scaled refresh:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL <contact>"
python scripts/universe/build_universe.py --mode sec_listed_core --limit 250 --include-starter --output-dir data/universe
python scripts/run_etl.py --universe data/universe/universe.json --limit 250 --skip-backtest
python scripts/benchmark_growth_spurt.py
python scripts/build_search_index.py --universe data/universe/universe.json --limit 250
python scripts/forecast/run_forecast_pipeline.py --summary
python scripts/pipeline_health.py
```

Full or near-full universe refresh:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL <contact>"
$env:BALANCE_SHEET_SCORING_MODE="official"
$env:GROWTH_SPURT_MODE="display"
python scripts/pipeline/run_checkpointed_etl.py --universe data/universe/universe.json --limit all --batch-size 10 --max-workers 5 --fetch-only --skip-backtest
powershell -ExecutionPolicy Bypass -File scripts/pipeline/diagnose_checkpointed_etl.ps1
python scripts/pipeline/run_checkpointed_etl.py --universe data/universe/universe.json --limit all --batch-size 10 --merge-only --skip-backtest
python scripts/forecast/run_forecast_pipeline.py --summary --scaled-fast
python scripts/pipeline_health.py
```

Operational notes:

- `scripts/pipeline/run_checkpointed_etl.py` is a safety wrapper around the existing ETL, not a scoring rewrite.
- Fetch mode writes raw provider checkpoints under `data/checkpoints/etl_raw/`; this path is ignored by Git.
- Each ticker completion rewrites the active batch checkpoint atomically and updates a small `batch_*.status.json` sidecar, so interruption should lose at most the current provider request and diagnostics do not need to parse huge raw checkpoints.
- `--max-workers 5` allows up to five tickers to fetch concurrently inside one coordinated process. Do not run multiple independent checkpoint fetch processes against the same checkpoint directory.
- Merge mode replays completed checkpoints through the existing `scripts/run_etl.py` scoring/export path so official percentiles/signals are still computed over the selected universe in one global pass.
- Merge mode blocks incomplete checkpoint sets unless `--allow-partial-merge` is passed deliberately.
- SEC Company Facts payloads for mega-caps can be tens of MB per ticker, so a true 6,000-company fundamentals refresh is bandwidth- and time-heavy.
- Future checkpoint fetches default to the same 5-year Yahoo price window as `scripts/run_etl.py`. The first completed 5,799-stock checkpoint run used shorter provider-default price histories, so the scaled-fast forecast path is current-only and uses sparse historical scenario fallback instead of expensive model retraining.
- The weekday GitHub Action is still capped for runner safety. Scheduled runs validate health but do not commit public artifacts; manual dispatch is required for artifact commits while the deployed dataset is full-universe. Do not let a capped scheduled refresh overwrite a manually published 5,799-stock artifact set without an incremental refresh plan.

---

## 14. Validation checklist

Before commit/deploy after scoring, ETL, forecast, or projection work:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/benchmark_growth_spurt.py
python scripts/audit_backtest.py
python scripts/audit_search.py
python scripts/forecast/audit_training_dataset.py
python scripts/forecast/evaluate_models.py
python scripts/forecast/audit_forecasts.py
python scripts/pipeline_health.py
npm run test:brief
npm run typecheck
npm run build
```

For the current 5,799-stock scaled-fast forecast artifacts, use this forecast validation instead of expensive full retraining:

```powershell
python -m unittest tests.test_forecast_pipeline -v
python scripts/forecast/audit_forecasts.py
```

Expected caveats:

- `pipeline_health.py` can return partial success and still exit successfully if no critical failure exists.
- `audit_backtest.py` can pass an intentionally unavailable scaled backtest.
- Forecast model selection should remain baseline unless promotion is explicitly enabled and reviewed.

---

## 15. Where future financial instructions usually land

Map incoming financial/product instructions into one of these buckets:

| Instruction type | Likely files | Key risk |
|---|---|---|
| Display-only metric | React component + TypeScript type | accidentally implying recommendation |
| New data provider | `scripts/providers/`, ETL, artifacts, audits | fabricating unsupported values |
| Feature engineering | `scripts/features.py`, docs, tests | changing score inputs without disclosure |
| Official scoring change | `scripts/scoring.py`, scoring docs/tests/comparison | label drift without baseline comparison |
| Balance-sheet scoring change | `scripts/balance_sheet.py`, `scripts/scoring.py` | double-counting risk |
| Forecast/projection change | `scripts/forecast/`, `src/lib/position-projections.ts` | presenting scenario as prediction |
| Retrieval/RAG change | `scripts/build_search_index.py`, `rag/`, search UI | LLM overriding deterministic signal |

Preferred workflow:

1. checkpoint if the change is risky;
2. implement the smallest modular change;
3. regenerate artifacts from scripts;
4. run targeted tests;
5. run full validation before commit/deploy;
6. update this map and the blueprint.

---

## 16. Do-not-break list

- Preserve cautious research/educational disclaimers.
- Keep official signal deterministic.
- Keep LLM/RAG interpretation separate from official signal.
- Keep risk scores in the unfavorable direction.
- Keep missing values as `null`, not zero.
- Keep per-ticker ETL failures isolated and visible.
- Keep generated artifacts reproducible from scripts.
- Keep production free from local Ollama dependency.
- Keep analyst target fields unsupported/null until a real provider exists.
- Keep `frontend.md` out of ValueSignal work; it is unrelated DamLogics material unless the user explicitly says otherwise.
