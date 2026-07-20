# ValueSignal Technical Map

**Purpose:** Fast handoff for an accompanying ChatGPT or mini-model that is giving financial/product instructions to Codex.  
**Companion document:** `docs/ValueSignal_Project_Blueprint.md`  
**Last mapped from code:** 2026-07-20  
**Current local branch when mapped:** `scale-universe-foundation`  
**Current local commit when mapped:** `2243a40 feat: add experimental forecast projections`

This document is about how ValueSignal actually turns market/SEC observations into public research signals, forecast displays, saved-stock projections, and evidence panels. Treat code, tests, workflow YAML, and generated artifacts as source of truth if this document becomes stale.

## 1. Product boundary

ValueSignal is a research-support system, not a trading bot.

The product should:

- classify companies into cautious research signals;
- expose the score mechanics behind each signal;
- show which evidence is missing or stale;
- make balance-sheet risks visible instead of hiding them inside one score;
- support saved watchlist/portfolio research notes;
- provide experimental 30-day and 90-day research projections only when generated artifacts exist;
- retrieve and summarize SEC filing passages, with RAG kept separate from the deterministic signal engine.

The product must not:

- issue buy/sell/hold instructions;
- guarantee price movement;
- let an LLM overwrite the official signal;
- fabricate analyst targets, financial facts, filings, or model confidence;
- hide missing evidence behind zeros.

## 2. Current implementation snapshot

The local app is a Next.js 15 application with generated JSON artifacts under `public/data`.

Current important state:

- Branch: `scale-universe-foundation`
- Latest implementation commit: `2243a40 feat: add experimental forecast projections`
- Public preview tickers: `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `JPM`, `JNJ`, `XOM`, `F`, `KO`, `INTC`
- Full universe access: behind Google sign-in
- Current generated stock detail artifacts: 254 ticker files in `public/data/stocks`
- Current generated forecast artifacts: 254 ticker files in `public/data/forecasts`
- Current forecast validation status: `experimental`
- Current selected forecast models: zero-return baseline for both 30-day and 90-day artifacts
- Current analyst target provider status: unsupported; fields are typed but intentionally null

Uncommitted items that existed when this map was written:

- `data/reports/scoring_comparison_report.json`
- `logs/`
- `phases/`

Do not assume those are part of the technical map unless the user explicitly asks to include or commit them.

## 3. Main data flow

The pipeline is intentionally modular:

```text
Universe builder
  -> price provider
  -> SEC companyfacts provider
  -> cleaning and normalization
  -> raw feature derivation
  -> cross-sectional percentiles
  -> deterministic scoring
  -> balance-sheet official adjustment
  -> generated JSON artifacts
  -> Next.js dashboard / stock pages / saved stocks

SEC filings
  -> filing download
  -> HTML/text cleaning
  -> section-aware chunking
  -> BM25 index
  -> evidence panel / local RAG context

Stock price history artifacts
  -> experimental forecast training rows
  -> horizon model evaluation
  -> forecast artifacts
  -> saved-stock 30/90 projection display
```

Generated frontend-facing artifacts:

- `public/data/dashboard.json`
- `public/data/stocks/summary.json`
- `public/data/stocks/{TICKER}.json`
- `public/data/features.json`
- `public/data/signals.json`
- `public/data/backtest_results.json`
- `public/data/etl_report.json`
- `public/data/universe_coverage_report.json`
- `public/data/search_index.json`
- `public/data/search/{TICKER}.json`
- `public/data/forecasts/summary.json`
- `public/data/forecasts/{TICKER}.json`

Generated internal/audit artifacts:

- `data/fundamentals/balance_sheets/{TICKER}.json`
- `data/fundamentals/balance_sheets/manifest.json`
- `data/reports/balance_sheet_coverage_report.json`
- `data/reports/balance_sheet_scoring_official_change_report.json`
- `data/reports/forecast_model_leaderboard.json`
- `data/reports/forecast_backtest_30_day.json`
- `data/reports/forecast_backtest_90_day.json`
- `data/reports/forecast_data_quality.json`
- `data/reports/forecast_leakage_audit.json`
- `models/forecast/30_day/metadata.json`
- `models/forecast/90_day/metadata.json`

Do not manually edit `public/data/*.json` as source data. They are generated artifacts.

## 4. Universe and access model

The project started with a 10-stock public universe. It now has a scaled universe path while preserving the original 10 as the public preview.

Current public preview list is defined in:

- `src/lib/public-universe.ts`

Current dashboard behavior:

- `src/app/dashboard/page.tsx` is dynamic because authentication changes visibility.
- Unauthenticated users see only the original 10 preview tickers.
- Authenticated users see the scaled universe.
- `src/features/dashboard/StockTable.tsx` shows a lock/fade panel with Google sign-in when additional companies are hidden.

Current stock-detail behavior:

- `src/app/stock/[ticker]/page.tsx` blocks non-preview company pages for unauthenticated users.
- Locked stock pages show `UniverseLockPanel`.
- Public preview company pages remain accessible without login.

This is a product gate, not a scoring gate. The ETL still generates full-universe artifacts.

## 5. Raw features used by official scoring

Feature code lives in:

- `scripts/features.py`
- `docs/feature_dictionary.md`

Core official feature schema version:

- `FEATURE_SCHEMA_VERSION = "1.0.0"`

The official score engine uses 10 primary features:

| Feature | Group | Direction before scoring |
|---|---|---|
| `return_30d` | Momentum | higher recent return is stronger momentum |
| `return_90d` | Momentum | higher recent return is stronger momentum |
| `annualized_volatility` | Market risk | higher is riskier |
| `max_drawdown_1y` | Market risk | more negative is riskier; inverted during scoring |
| `earnings_yield` | Value | higher is stronger value evidence |
| `sales_yield` | Value | higher is stronger value evidence |
| `liabilities_to_assets` | Balance-sheet risk v1 input | higher is riskier |
| `revenue_growth` | Quality | higher is stronger quality evidence |
| `net_margin` | Quality | higher is stronger quality evidence |
| `net_margin_trend` | Quality | higher is stronger quality evidence |

Additional display/context fields currently derived from SEC facts:

- latest price;
- daily change percent;
- market cap;
- liabilities/assets;
- latest revenue;
- revenue growth;
- gross profit;
- gross margin;
- net margin.

Important mechanics:

- Returns use adjusted close when present, raw close otherwise.
- Annual fundamentals use latest-filed 10-K facts for each fiscal period.
- Missing inputs stay `null`; they are not converted to zero.
- Out-of-range values are winsorized for percentile scoring but preserved in `rangeWarnings`.
- Percentiles are cross-sectional within the current universe batch.
- Missing features lower confidence separately from score computation.

## 6. Component score mechanics

Scoring code lives in:

- `scripts/scoring.py`
- `docs/scoring_specification.md`

Score schema version:

- `SCORE_SCHEMA_VERSION = "1.0.0"`

Each component score is bounded to 0-100.

Weights:

| Component | Inputs | Direction |
|---|---|---|
| Value | `earnings_yield` 60%, `sales_yield` 40% | higher is better |
| Quality | `net_margin` 45%, `revenue_growth` 30%, `net_margin_trend` 25% | higher is better |
| Momentum | `return_90d` 60%, `return_30d` 40% | higher is better |
| Market risk | `max_drawdown_1y` 55%, `annualized_volatility` 45% | higher score is worse |
| Balance-sheet risk | `liabilities_to_assets` 100%, later blended with balance-sheet risk penalty in official mode | higher score is worse |

Score construction:

1. Compute winsorized cross-sectional percentile per feature.
2. Apply directionality.
3. Drop missing inputs from the component.
4. Renormalize remaining weights.
5. Sum weighted points.
6. Bound score to 0-100.

Risk convention:

- `value`, `quality`, and `momentum`: higher is stronger.
- `marketRisk`, `balanceSheetRisk`, and `momentumRisk`: higher is worse.
- `momentumRisk = 100 - momentum`.

Every component stores contribution rows:

- feature name;
- raw percentile;
- directed percentile;
- normalized weight;
- contributed points.

Frontend display:

- `src/components/ScoreBreakdown.tsx`
- `src/features/stock-detail/ScoreCard.tsx`
- `src/components/AnalystSummary.tsx`

## 7. Confidence mechanics

Confidence is feature availability, not prediction confidence.

Current rule in `scripts/scoring.py`:

| Available official features | Confidence |
|---:|---|
| 9-10 | High |
| 7-8 | Medium |
| 5-6 | Low |
| fewer than 5 | Insufficient |

Balance-sheet scoring can adjust confidence in official mode:

- complete and usable balance sheet can add a small confidence improvement;
- missing core fields or unavailable balance sheet can reduce confidence;
- severe balance-sheet gate combinations can further reduce confidence.

Do not describe confidence as model certainty or expected-return reliability.

## 8. Official signal classification

The official deterministic signal is assigned in `scripts/scoring.py`.

Current classification priority:

1. `insufficient-evidence`
   - if confidence is insufficient.
2. `value-trap-risk`
   - if value is strong enough but balance-sheet risk is high.
3. `momentum-risk`
   - if momentum risk is high.
4. `potentially-undervalued`
   - if value is strong, quality is acceptable, and major market/balance-sheet risks are not elevated.
5. `quality-watchlist`
   - if quality is strong and balance-sheet risk is not elevated.
6. `neutral`
   - all other combinations.

Design intent:

- Risk labels take priority over positive labels.
- A cheap stock with a weak balance sheet should not be marketed as simply undervalued.
- Missing evidence should never be forced into a confident label.
- Labels are research categories, not recommendations.

Signal definitions live in multiple places:

- `docs/ValueSignal_Project_Blueprint.md`
- `rag/stock_context.py`
- `src/data/signals.ts`
- `src/types/signal.ts`

Keep these aligned when changing signal language.

## 9. Balance-sheet scoring mechanics

Balance-sheet code lives in:

- `scripts/balance_sheet.py`
- `docs/balance_sheet_scoring.md`

Balance-sheet scoring mode currently defaults to:

- `BALANCE_SHEET_SCORING_MODE=official`

Supported modes:

- `off`
- `shadow`
- `experimental`
- `official`

The balance-sheet layer keeps standalone artifacts intact while also influencing official scoring when mode is `official`.

### 9.1 SEC balance-sheet extraction

The balance-sheet extractor selects a reference SEC companyfacts filing context from recent 10-K/10-Q facts. It prefers facts matching the selected accession and period end, but can fall back to same-period/latest facts while warning about it.

Core extracted fields include:

- assets;
- current assets;
- cash and equivalents;
- short-term investments;
- accounts receivable;
- inventory;
- PP&E;
- goodwill;
- intangible assets;
- liabilities;
- current liabilities;
- accounts payable;
- short-term debt;
- long-term debt;
- stockholders' equity;
- retained earnings.

Missing fields remain `null` and are listed in `missingFields`.

### 9.2 Balance-sheet metrics

Derived metrics include:

- current ratio;
- quick ratio;
- cash ratio;
- working capital;
- debt/equity;
- debt/assets;
- equity ratio;
- cash/debt;
- net debt;
- goodwill + intangibles/assets;
- short-term debt share;
- book value;
- book value/share;
- price/book;
- retained earnings.

### 9.3 Balance-sheet sub-scores

Target comparisons use status bands:

- healthy;
- acceptable;
- caution;
- risk;
- severe risk;
- unavailable.

The layer produces:

- `liquidityScore`;
- `leverageScore`;
- `solvencyScore`;
- `assetQualityScore`;
- `balanceSheetQualityScore`;
- `balanceSheetRiskPenalty`.

Direction:

- `balanceSheetQualityScore`: higher is better.
- `balanceSheetRiskPenalty`: higher is worse.

### 9.4 Balance-sheet risk gates

Current gates:

- Liquidity Risk Gate
- Severe Liquidity Risk Gate
- High Leverage Gate
- Severe Leverage Gate
- Negative Equity Gate
- Debt Maturity Pressure Gate
- Asset Quality Warning Gate
- Balance Sheet Incomplete Gate

These gates are shown on stock detail pages through:

- `src/components/BalanceSheetHealth.tsx`

### 9.5 Official blend

When mode is `official`, the score engine:

- blends `balanceSheetRiskPenalty` into `scores.balanceSheetRisk`;
- lightly blends `balanceSheetQualityScore` into `scores.quality`;
- adjusts confidence;
- appends balance-sheet reason codes;
- can reroute strong value plus severe balance-sheet weakness toward `value-trap-risk`;
- emits `balanceSheetOfficialChange` so signal changes are auditable.

Current blend rule in code:

- balance-sheet risk becomes 50% prior `liabilities_to_assets` risk and 50% balance-sheet risk penalty when both exist;
- quality becomes 85% prior quality and 15% balance-sheet quality when both exist.

If future financial instructions want a different balance-sheet influence, change this deliberately, update tests, and compare against the v1 scoring checkpoint/baseline.

## 10. Reason codes and evidence language

Reason codes are generated in `scripts/scoring.py` and translated for frontend display in:

- `src/lib/scoreExplanations.ts`

Important reason-code families:

- `VALUE_STRONG`
- `VALUE_WEAK`
- `QUALITY_STRONG`
- `QUALITY_WEAK`
- `MOMENTUM_RISK_HIGH`
- `MARKET_RISK_HIGH`
- `BALANCE_SHEET_RISK_HIGH`
- `BALANCE_SHEET_GATE_TRIGGERED`
- `BALANCE_SHEET_SUPPORTIVE`
- `EVIDENCE_SPARSE`
- `EVIDENCE_PARTIAL`
- `EVIDENCE_COMPLETE`

Frontend splits these into supporting and weakening evidence on stock detail pages.

If a new score component is added, add:

1. raw feature derivation;
2. feature docs;
3. scoring weights;
4. reason codes;
5. frontend explanation mapping;
6. tests;
7. audit checks.

## 11. Backtesting mechanics

Backtest code lives in:

- `scripts/backtest.py`
- `scripts/audit_backtest.py`
- `docs/backtesting_protocol.md`

Current protocol:

- benchmark: `SPY`;
- execution lag: 1 session;
- forward horizons: 30, 60, 90 sessions;
- snapshot frequency: every 21 sessions;
- point-in-time rule: only prices and filings available on or before the signal date are used.

Backtest outputs:

- observations by ticker, signal, horizon, entry date, outcome date;
- forward return;
- benchmark return;
- excess return;
- adverse drawdown;
- cohort aggregates by signal, horizon, and market regime;
- bias audit with leakage and alignment rejection counts.

Current scaled scheduled ETL uses `--skip-backtest`, so `public/data/backtest_results.json` may be an unavailable/insufficient report during scaled artifact refreshes. Do not mistake that for a scoring failure.

Known stale wording risk:

- `scripts/backtest.py` still contains legacy limitation strings mentioning the original ten-company starter list. The user has already asked to update this language for the scaled universe. If touched, replace with current scaled-universe limitations: survivorship/composition bias, artifact batch limit, provider coverage gaps, transaction costs/taxes/slippage excluded, overlapping windows, and descriptive intervals only.

## 12. Experimental forecast and position projection layer

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

### 12.1 What the forecast currently is

The forecast layer is experimental and price-history-first.

It builds point-in-time rows from existing stock `priceHistory` artifacts:

- feature date;
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

Target construction:

- 30-day target uses first market session on or after `featureDate + 30 calendar days`.
- 90-day target uses first market session on or after `featureDate + 90 calendar days`.

Data split:

- by feature date, never random;
- embargo before validation/test windows using horizon length;
- no future analyst targets;
- no future scoring labels.

Candidate models:

- zero-return baseline;
- historical-mean baseline;
- market-return baseline;
- ridge regression;
- elastic net;
- huber regression;
- histogram gradient boosting;
- random forest challenger;
- CatBoost marked unavailable unless explicitly installed later;
- small neural network disabled for lightweight local batch.

Current selected model in generated artifacts:

- 30-day: zero-return baseline;
- 90-day: zero-return baseline.

This means current base VS return estimate is `0.0` in generated artifacts, while lower/upper ranges come from residual quantiles. That is conservative and intentional until a challenger proves itself.

### 12.2 What the forecast is not

The forecast layer is not a validated price prediction system.

It currently does not use:

- point-in-time financial feature snapshots;
- analyst consensus target data;
- earnings forecasts;
- macro data;
- options-implied probabilities;
- sector-relative target revisions;
- RAG/LLM labels.

### 12.3 Saved-stock projection display

Saved positions support:

- watchlist items;
- portfolio positions;
- owned vs planned status;
- share quantity;
- dollar allocation amount;
- user-entered 30/90 scenario fields;
- VS-generated 30/90 projections when forecast artifacts exist.

Projection math:

- If quantity type is `dollar_amount`, current position value equals the dollar amount.
- If quantity type is `shares`, current position value equals shares times forecast current price.
- 30/90 base change equals current position value times forecast return estimate.
- 30/90 base value equals current position value times `1 + forecast return estimate`.
- Lower/upper ranges use forecast lower/upper returns.

Current market target field:

- `analystTarget` exists in forecast artifacts as a typed object.
- Status is currently `unsupported`.
- Target mean and implied return are null until a legitimate market-data provider is added.
- Do not fabricate market target values.

The UI should distinguish:

1. ValueSignal model estimate;
2. market/analyst target estimate;
3. user scenario;
4. unavailable reason.

## 13. SEC filing retrieval and BM25

Search/index code lives in:

- `scripts/build_search_index.py`
- `scripts/chunk_filings.py`
- `scripts/text_cleaning.py`
- `scripts/retrieval.py`
- `scripts/audit_search.py`
- `src/lib/search.ts`
- `src/app/api/search/route.ts`
- `src/components/FilingEvidencePanel.tsx`

Current search schema:

- `SEARCH_SCHEMA_VERSION = "3.0.0"`

Pipeline:

```text
SEC recent filings
  -> clean HTML
  -> section-aware chunks
  -> BM25 index
  -> per-ticker partition files
  -> frontend evidence search
```

BM25 behavior:

- tokenization is deterministic;
- stopwords removed;
- default `k1 = 1.5`, `b = 0.75`;
- per-ticker index files live under `public/data/search`;
- `public/data/search_index.json` is a manifest in partitioned mode;
- diversification happens after ranking and does not mutate BM25 scores.

Frontend search expansion currently broadens common queries:

- risk / risk analysis;
- supply chain;
- liquidity/debt/capital;
- cybersecurity;
- competition/demand/revenue/margin.

Important boundary:

- Query expansion can broaden recall.
- It cannot invent passages if the filing index lacks matching chunks.
- “No matching passage found” can mean the ticker has no indexed filing, a weak query, or genuinely absent evidence.

## 14. Local RAG boundary

RAG code lives in:

- `rag/`
- `scripts/run_rag.py`
- `scripts/build_rag_embeddings.py`
- `src/app/api/rag/route.ts`
- `src/app/rag/page.tsx`
- `src/components/LocalRagConsole.tsx`
- `docs/rag_specification.md`

Current boundary:

- Production should not depend on local Ollama.
- `src/lib/rag-availability.ts` keeps local RAG dev-only unless explicitly enabled.
- RAG uses SEC evidence and structured stock context.
- RAG can explain, support, weaken, or complicate the deterministic signal.
- RAG must not overwrite the official signal.

RAG has intent handling for risk/outlook questions:

- go up/down;
- hold value;
- price direction;
- downside risk;
- upside support;
- recovery;
- signal strong enough.

Required risk-outlook behavior:

- refuse price prediction;
- still answer as a risk-based research assessment;
- include deterministic signal context;
- retrieve both weakening and supporting evidence;
- cite chunk IDs;
- keep official signal separate from RAG interpretation.

Allowed evidence assessment values:

- Supports signal
- Weakens signal
- Mixed evidence
- Insufficient evidence
- Review recommended

## 15. Authentication and saved-stock data

Auth code lives in:

- `src/lib/auth.ts`
- `src/lib/auth-client.ts`
- `src/lib/auth-config.ts`
- `src/lib/server-auth.ts`
- `src/app/api/auth/[...all]/route.ts`
- `src/components/AuthStatus.tsx`
- `src/components/GoogleSignInButton.tsx`

Saved user-data code lives in:

- `src/lib/user-data-store.ts`
- `src/app/api/watchlist/route.ts`
- `src/app/api/watchlist/[ticker]/route.ts`
- `src/app/api/portfolio/route.ts`
- `src/app/api/portfolio/[positionId]/route.ts`
- `src/types/user-records.ts`

Current auth purpose:

- prepare protected AI/RAG features;
- gate full universe access;
- enable personal watchlist/portfolio research notes.

Required environment variables exist outside Git:

- `BETTER_AUTH_SECRET`
- `BETTER_AUTH_URL`
- `NEXT_PUBLIC_BETTER_AUTH_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `DATABASE_URL`

Never commit real secret values.

## 16. Scheduled workflow

GitHub Actions workflow:

- `.github/workflows/refresh-data.yml`

Schedule:

- weekday cron at `25 23 * * 1-5`

Current workflow steps:

1. checkout;
2. setup Python 3.12;
3. setup Node 24;
4. install Python dependencies;
5. validate `VS_CONTACT_EMAIL`;
6. run Python tests;
7. run brief generator tests;
8. build scaled universe;
9. refresh live ETL artifacts;
10. refresh SEC filing BM25 index;
11. refresh experimental forecast artifacts;
12. audit features;
13. audit scoring;
14. audit backtest;
15. audit filing search;
16. audit forecast outputs;
17. commit changed generated artifacts as `data: refresh ValueSignal artifacts`;
18. push.

Current workflow environment:

- `VS_USER_AGENT = ValueSignal research ETL ${{ secrets.VS_CONTACT_EMAIL }}`
- `BALANCE_SHEET_SCORING_MODE = official`
- `VS_UNIVERSE_MODE = sec_listed_core`
- `VS_UNIVERSE_PATH = data/universe/universe.json`
- `VS_UNIVERSE_LIMIT = 250`

Important prior failure mode:

- If `data/universe/universe.json` does not exist before `scripts/run_etl.py`, the ETL fails with `FileNotFoundError`.
- The workflow now builds the scaled universe before ETL.

Deployment behavior:

- When the workflow pushes generated artifact commits to the deployment branch, Vercel should redeploy.
- The frontend consumes JSON at build/runtime depending on route behavior.
- Dynamic auth-gated pages use server-side reads of generated JSON, but deployment still needs fresh artifacts in the repo unless external storage is added later.

## 17. Commands

Use these from the repo root.

Local app:

```powershell
npm run dev
npm run typecheck
npm run build
```

Python tests and audits:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/audit_backtest.py
python scripts/audit_search.py
```

ETL:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL your-contact-email@example.com"
python scripts/universe/build_universe.py --mode sec_listed_core --limit 250 --include-starter --output-dir data/universe
python scripts/run_etl.py --universe data/universe/universe.json --limit 250 --skip-backtest
python scripts/build_search_index.py --universe data/universe/universe.json --limit 250
```

Forecast:

```powershell
python scripts/forecast/run_forecast_pipeline.py --summary
python scripts/forecast/audit_training_dataset.py
python scripts/forecast/evaluate_models.py
python scripts/forecast/audit_forecasts.py
```

RAG local smoke tests:

```powershell
python scripts/run_rag.py "should i expect this to hold value or go up or down? assess based on risk data" --ticker AAPL --mode hybrid --top-k 6 --depth deep
python scripts/run_rag.py "is the signal strong enough?" --ticker F --mode hybrid --top-k 5
```

Scoring comparison:

```powershell
python scripts/compare_scoring_outputs.py
```

## 18. Validation gates by subsystem

### ETL

Pass conditions:

- provider failures are logged per ticker;
- one ticker failure does not stop the run;
- output paths exist;
- `public/data/dashboard.json`, `features.json`, `signals.json`, and `etl_report.json` are valid JSON;
- row counts and failed symbols appear in `etl_report.json`;
- `VS_USER_AGENT` includes a contact email.

Debug checklist:

- inspect HTTP status and headers;
- check ticker-to-CIK mapping;
- compare units and fiscal periods;
- validate output path;
- diff schema against frontend types.

### Features

Pass conditions:

- price ordering is chronological;
- 30/90 returns use the intended lookback;
- annualization factor is `sqrt(252)`;
- denominator signs are handled;
- outliers are traceable to raw rows;
- missing values remain null.

Debug checklist:

- verify price ordering;
- inspect annualization factor;
- check denominator signs;
- trace outliers to raw rows.

### Scoring

Pass conditions:

- every score remains 0-100 or null;
- labels are deterministic;
- risk direction is correct;
- missing evidence reduces confidence;
- reason codes align with score/risk thresholds.

Debug checklist:

- print weighted contributions;
- test exact boundaries;
- confirm null branch;
- compare reason codes to score.

### Balance sheet

Pass conditions:

- standalone balance-sheet artifacts remain intact;
- missing fields are listed, not filled;
- target bands are auditable;
- risk gates are visible;
- official blend is traceable through `balanceSheetOfficialChange`;
- comparison against baseline is run when changing official scoring.

Debug checklist:

- inspect selected filing accession and period end;
- compare extracted fields to SEC companyfacts;
- review missing core fields;
- inspect triggered gates;
- run scoring comparison report.

### Retrieval

Pass conditions:

- index has documents;
- per-ticker search files exist;
- BM25 status flags update dashboard/stocks/coverage artifacts;
- citation metadata includes ticker, form, filing date, section, URL, and chunk ID;
- retrieval returns real chunks or a clear unavailable state.

Debug checklist:

- run `python scripts/audit_search.py`;
- inspect `public/data/search_index.json`;
- inspect `public/data/search/{TICKER}.json`;
- test broad terms like risk, liquidity, revenue, supply chain;
- check whether ticker is indexed before blaming query logic.

### Forecast

Pass conditions:

- training rows are generated from existing price history;
- 30/90 targets use future market sessions after calendar horizons;
- split is date-based and embargoed;
- output returns are above -100%;
- lower/base/upper ordering is valid;
- forecast artifact count matches stock artifact count when all stocks have price history;
- validation status remains `experimental` unless explicitly promoted after review.

Debug checklist:

- run forecast audits;
- inspect `data/reports/forecast_model_leaderboard.json`;
- inspect one ticker artifact in `public/data/forecasts`;
- confirm analyst target status is unsupported unless a provider has been added;
- confirm frontend handles zero return as available, not missing.

### Frontend integration

Pass conditions:

- `npm run typecheck` passes;
- `npm run build` passes;
- dashboard shows preview/full universe correctly by auth state;
- stock detail pages block non-preview tickers when signed out;
- saved portfolio supports share quantity and dollar allocation;
- missing generated forecast artifacts produce explicit reasons.

## 19. How to safely accept future financial instructions

When a financial/product instruction arrives from the accompanying ChatGPT, map it into one of these buckets before editing:

1. Display-only change
   - Example: show 30/90 VS estimate beside market target.
   - Usually touches React components, types, and generated artifact reading.
   - Should not change scoring.

2. New input data
   - Example: add analyst consensus target provider.
   - Touches provider, ETL, artifact schema, audit, and disclosure.
   - Must not fabricate values if provider data is unavailable.

3. Feature-engineering change
   - Example: add gross margin trend.
   - Touches `scripts/features.py`, docs, tests, generated artifacts, and frontend display.
   - Does not automatically affect official score unless scoring weights are changed.

4. Scoring change
   - Example: make balance-sheet liquidity stronger in value-trap classification.
   - Touches `scripts/scoring.py`, tests, docs, reason codes, comparison reports.
   - Must run scoring audits and compare against baseline.

5. Forecast/modeling change
   - Example: promote ridge regression if it beats baseline.
   - Touches `scripts/forecast`, artifacts, audits, and forecast disclosure.
   - Must keep validation status honest.

6. RAG/intelligence change
   - Example: explain whether SEC evidence supports the official signal.
   - Touches `rag/`, RAG route/UI, and retrieval tests.
   - Must not overwrite official signal.

Preferred workflow:

1. checkpoint current state if the change is risky;
2. implement the smallest modular change;
3. regenerate only needed artifacts;
4. run targeted tests;
5. run full validation before commit/deploy;
6. document if score or artifact schema behavior changed.

## 20. Guardrails for the next 30/90 earnings/return display work

The user wants the app to show:

- ValueSignal estimate of 30-day return;
- ValueSignal estimate of 90-day return;
- market target value based return for 30 days;
- market target value based return for 90 days.

Current truth:

- VS 30/90 artifacts exist and are experimental.
- Current base VS return is zero-return baseline in generated artifacts.
- Current lower/upper ranges exist and are residual-quantile ranges.
- Market/analyst target fields exist but are unsupported/null.
- There is no legitimate analyst target provider yet.

Safe next implementation path:

1. Keep VS estimate and analyst/market target return visually separate.
2. Show `Unavailable: analyst target provider not configured` instead of null-looking blank boxes.
3. If adding market target provider, add a provider module and artifact audit first.
4. Do not convert an analyst 12-month target into a 30/90-day target unless the artifact explicitly records the horizon and methodology.
5. If the instruction asks for “earnings display,” clarify whether it means:
   - expected return;
   - earnings/revenue/gross margin fundamentals;
   - earnings calendar;
   - EPS estimates;
   - portfolio dollar gain/loss.

## 21. Files most likely to matter next

For 30/90 projection display:

- `src/components/SavedStocksConsole.tsx`
- `src/lib/position-projections.ts`
- `src/types/forecast.ts`
- `public/data/forecasts/summary.json`
- `public/data/forecasts/{TICKER}.json`
- `scripts/forecast/pipeline.py`
- `tests/test_forecast_pipeline.py`

For analyst/market target values:

- new provider module should be added under `scripts/providers/`;
- forecast artifact schema should be extended in `src/types/forecast.ts`;
- audit should reject stale, missing, or horizon-ambiguous target values;
- UI should display source date, provider, analyst count, and unavailable reason.

For official scoring:

- `scripts/scoring.py`
- `scripts/features.py`
- `scripts/balance_sheet.py`
- `docs/scoring_specification.md`
- `docs/balance_sheet_scoring.md`
- `src/lib/scoreExplanations.ts`
- `tests/test_scoring.py`
- `tests/test_balance_sheet.py`

For public/full universe gating:

- `src/lib/public-universe.ts`
- `src/app/dashboard/page.tsx`
- `src/app/stock/[ticker]/page.tsx`
- `src/features/dashboard/StockTable.tsx`
- `src/components/UniverseLockPanel.tsx`

## 22. Do-not-break list

- Keep all decision surfaces covered by research/educational disclaimers.
- Keep signal classification deterministic.
- Keep LLM/RAG interpretation separate from official signal.
- Keep risk scores in the unfavorable direction.
- Keep missing financial values as null, not zero.
- Keep per-ticker ETL failures isolated and logged.
- Keep generated artifacts reproducible from scripts.
- Keep production free from local Ollama dependency.
- Keep secrets out of docs, commits, logs, and artifacts.
- Keep `frontend.md` out of ValueSignal planning unless the user explicitly says otherwise; it is unrelated DamLogics material.

