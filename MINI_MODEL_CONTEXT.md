# ValueSignal Mini-Model Context

Use this briefing for small debugging, maintenance, and implementation tasks. If it conflicts with the repository, code, tests, workflow YAML, and generated artifacts are the source of truth.

## Product intent

ValueSignal is a cautious public-company research tool. It organizes valuation, quality, momentum, market-risk, balance-sheet-risk, filing evidence, backtests, saved-position scenarios, and recent trend tags into transparent research views.

It is not a trading bot, financial advisor, or source of buy/sell/hold recommendations. Keep educational-use disclaimers visible at decision surfaces. Describe outputs as signals, evidence, risks, caveats, scenarios, or historical observations.

## Current state

- Product shell, dashboard, stock detail, methodology, auth, saved stocks, and responsive layouts exist.
- Scaled universe artifacts currently cover 245 active stock detail files.
- The original public preview tickers remain: AAPL, MSFT, GOOGL, AMZN, JPM, JNJ, XOM, F, KO, INTC.
- The full scaled universe is gated behind Google sign-in.
- ETL uses provider-aware Python modules for Yahoo chart prices and SEC company facts.
- Official scoring remains deterministic: value, quality, momentum, market risk, balance-sheet risk, momentum risk, confidence, and one mutually exclusive signal.
- Balance-sheet-aware scoring is official, but standalone balance-sheet artifacts remain intact.
- BM25 SEC filing retrieval is production-safe; local Ollama/RAG remains local/experimental or a production placeholder.
- Saved-stock 30/90-day projections use approved forecast output when available, then conservative historical scenario fallback, then unavailable. Customer-facing cards are normalized `HoldingOutcome` records, not ad-hoc UI math.
- Market-target scenarios are separate from ValueSignal projections and currently unavailable because no analyst target provider is configured.
- Growth Spurt detector is display-only in v1. It does not alter official scoring or signals.

## Main architecture map

Frontend:

- `src/app/` - Next.js App Router pages and API routes.
- `src/features/dashboard/StockTable.tsx` - dashboard filters/table, including Growth Spurt filter.
- `src/app/stock/[ticker]/page.tsx` - stock detail page.
- `src/components/GrowthSpurtBadge.tsx` - compact badge and detail Recent Trend card.
- `src/components/HoldingOutcomeCard.tsx` - reusable saved-position outcome card/grid.
- `src/components/SavedStocksConsole.tsx` - user watchlist/portfolio/projection UI.
- `src/lib/etl.ts` - server-only generated JSON readers and shared artifact types.
- `src/lib/research.ts` - merges generated data with fallback stock fixtures.
- `src/types/stock.ts`, `src/types/forecast.ts`, `src/types/signal.ts` - frontend contracts.

Python/data pipeline:

- `scripts/run_etl.py` - main ETL boundary; writes dashboard/features/signals/stocks/ETL report.
- `scripts/features.py` - official feature engineering.
- `scripts/scoring.py` - official scoring and classification.
- `scripts/balance_sheet.py` - balance-sheet extraction and score/risk gates.
- `scripts/growth_spurt.py` - deterministic Growth Spurt formula and thresholds.
- `scripts/build_growth_spurt_artifacts.py` - repopulates Growth Spurt fields from existing generated price histories.
- `scripts/benchmark_growth_spurt.py` - point-in-time SPY benchmark for Growth Spurt.
- `scripts/build_search_index.py` - per-ticker BM25 index.
- `scripts/forecast/run_forecast_pipeline.py` - forecast/conservative scenario artifacts.
- `scripts/pipeline_health.py` - internal/public health reports.

Docs:

- `docs/ValueSignal_Technical_Map.md` - current detailed engineering/finance atlas.
- `docs/ValueSignal_Project_Blueprint.md` - durable session handoff and product protocol.
- `docs/feature_dictionary.md` - official features plus display-only Growth Spurt features.
- `docs/scoring_specification.md` - official score/signaling rules.
- `docs/backtesting_protocol.md` - official signal backtest and Growth Spurt benchmark protocol.
- `docs/artifact_schemas.md` - generated artifact schema map.

Do not use `frontend.md` for ValueSignal work. It is unrelated DamLogics material unless the user explicitly says otherwise.

## Data flow

```text
Universe JSON
  -> prices + SEC companyfacts
  -> cleaning/latest facts
  -> official features
  -> official scores/signals
  -> balance-sheet context
  -> display-only Growth Spurt artifact
  -> forecast/conservative scenario artifacts
  -> HoldingOutcome saved-position estimates
  -> generated public/data JSON
  -> Next.js server readers
  -> dashboard / stock detail / saved stocks / methodology
```

SEC filing flow:

```text
SEC filings
  -> clean text
  -> section-aware chunks
  -> per-ticker BM25 index
  -> evidence search / local RAG context
```

Generated artifacts are not hand-maintained source data. Change scripts, regenerate artifacts, and commit only intended generated outputs.

Important generated paths:

- `public/data/dashboard.json`
- `public/data/features.json`
- `public/data/signals.json`
- `public/data/stocks/summary.json`
- `public/data/stocks/{TICKER}.json`
- `public/data/etl_report.json`
- `public/data/universe_coverage_report.json`
- `public/data/backtest_results.json`
- `public/data/search_index.json`
- `public/data/search/{TICKER}.json`
- `public/data/forecasts/summary.json`
- `public/data/forecasts/{TICKER}.json`
- `public/data/pipeline_health.json`
- `data/reports/growth_spurt_benchmark.json`

## Growth Spurt detector v1

Meaning: recent prices have formed a relatively persistent and orderly upward trend. It is a historical-pattern detector, not a prediction.

Mechanics:

- adjusted close preferred, close fallback;
- 63-session primary window;
- 21-session confirmation window;
- Theil-Sen trend on log prices;
- SPY-relative returns required when available;
- score components: 30% direction, 25% consistency, 20% SPY-relative strength, 15% drawdown control, 10% confirmation/acceleration;
- one-day spike dominance triggers `ONE_DAY_SPIKE_DOMINATED` and prevents detected status;
- statuses: `detected`, `emerging`, `not_detected`, `unavailable`;
- insufficient history is `unavailable`, never zero;
- current generated counts: 245 attempted, 19 detected, 30 emerging, 187 not detected, 9 unavailable, 0 calculation failures.

Guardrail: do not blend Growth Spurt into official scoring without a later approved scoring-integration phase.

## Saved-position outcome cards

The saved-position UI shows four main cards:

- `ValueSignal 30 Days`
- `ValueSignal 90 Days`
- `Market Target 30 Days`
- `Market Target 90 Days`

Each available card should show total gain/loss once as the headline, then return, estimated sell price, estimated position value, gain/loss per share, source label, and a human-readable as-of date. Do not repeat total gain/loss as a body row.

Core formula:

```text
estimatedGainLossPerShare = estimatedSellPrice - currentPurchasePrice
estimatedTotalGainLoss = sharesHeld * estimatedGainLossPerShare
estimatedPositionValue = sharesHeld * estimatedSellPrice
```

For dollar-allocation mode, first calculate `impliedShares = dollarAllocation / currentPrice`, then use the same per-share formulas. Display that quantity as `Implied shares`, not `Shares held`. For share positions, display `Shares held`. Do not multiply a dollar allocation by the estimated sell price. Do not use "earnings" for a user's position outcome.

Unavailable ValueSignal cards should stay compact and use horizon-specific observation details, for example `Not enough historical data` plus `8 of 24 required observations` for 30 days or `8 of 12 required observations` for 90 days. Unavailable market-target cards should say `Analyst target data is not currently available.` and must not display provider/source/horizon implementation details.

Projection-source priority:

```text
approved non-baseline forecast model
  -> ValueSignal Conservative Historical Scenario
  -> unavailable with reason
```

Market-target scenarios can be calculated only from legitimate provider data with `targetMean`, `currentPriceAtCollection`, and a known `targetHorizonDays`. Current artifacts are `unsupported`; do not fabricate targets or substitute ValueSignal estimates.

Personal 30/90-day scenario fields are user-entered and must remain collapsed/separate. They do not overwrite ValueSignal or market-target outcomes.

## Commands

Run from repository root.

Frontend:

```powershell
npm run dev
npm run test:brief
npm run typecheck
npm run build
```

Python:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/audit_backtest.py
python scripts/audit_search.py
python scripts/build_growth_spurt_artifacts.py
python scripts/benchmark_growth_spurt.py
python scripts/pipeline_health.py
```

Scaled refresh:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL <CONTACT_EMAIL>"
$env:BALANCE_SHEET_SCORING_MODE="official"
$env:GROWTH_SPURT_MODE="display"
python scripts/universe/build_universe.py --mode sec_listed_core --limit 250 --include-starter --output-dir data/universe
python scripts/run_etl.py --universe data/universe/universe.json --limit 250 --skip-backtest
python scripts/benchmark_growth_spurt.py
python scripts/build_search_index.py --universe data/universe/universe.json --limit 250
python scripts/forecast/run_forecast_pipeline.py --summary
python scripts/pipeline_health.py
```

Use `--limit all` or omit `--limit` for an uncapped universe command only when that is intentional. Use staged batches for broader runs.

Never commit `.env*`, secrets, tokens, real credentials, model files, caches, or local logs.

## Scheduled refresh

`.github/workflows/refresh-data.yml` runs weekdays at `25 23 * * 1-5` UTC and supports manual dispatch.

It builds the scaled universe, runs ETL, benchmarks Growth Spurt, rebuilds BM25, refreshes forecasts, runs audits, publishes pipeline health, commits changed generated artifacts, and pushes. A pushed artifact commit triggers Vercel when automatic deployment is enabled.

Required GitHub secret:

- `VS_CONTACT_EMAIL`

Vercel auth/database variables are configured outside Git.

## Debugging checklist

ETL:

- Confirm `VS_USER_AGENT` contains a contact email.
- Confirm `data/universe/universe.json` exists before scaled ETL.
- Inspect `public/data/etl_report.json` for per-ticker failures.
- One ticker failure must not stop the batch.

Features/scoring:

- Missing inputs stay `null`.
- Scores stay 0-100.
- Risk scores are worse when higher.
- Official signal must remain deterministic.

Growth Spurt:

- Run `python -m unittest tests.test_growth_spurt -v`.
- Confirm statuses are distinct.
- Confirm spike-dominated moves are rejected.
- Confirm SPY-relative fields are present or unavailable is explicit.
- Confirm official `signals.json` does not change because of Growth Spurt.

Frontend:

- Compare generated keys with `src/lib/etl.ts` and `src/types/stock.ts`.
- Run `npm run test:brief`, `npm run typecheck`, and `npm run build`.
- Check mobile layout and long labels in dashboard/detail cards.

Saved outcomes:

- `src/lib/position-projections.ts` owns all ValueSignal and market-target calculations.
- Dollar allocations first convert to `impliedShares = dollarAllocation / currentPrice`, then use per-share gain/loss math.
- Share positions use `shares * (estimatedFuturePrice - currentPrice)`.
- Valid zero-dollar change must render `$0.00`, not `Unavailable`.
- Missing/stale/currently unsupported market targets must show a compact reason and keep unavailable scenario-source fields null.

## Handoff template

```markdown
Outcome: <what now works or what was diagnosed>

Changed files:
- <path>: <purpose>

Commands/checks:
- `<command>` - PASS/FAIL and important result

Generated artifacts:
- Regenerated: yes/no
- Files: <paths or none>

Remaining risks or follow-ups:
- <specific item, or none>
```
