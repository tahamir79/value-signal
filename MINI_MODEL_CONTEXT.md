# ValueSignal Mini-Model Context

Use this briefing for small debugging, maintenance, and implementation tasks. If it conflicts with the repository, code, tests, workflow YAML, and generated artifacts are the source of truth.

## Product intent

ValueSignal is a cautious public-company research tool. It organizes valuation, quality, momentum, market-risk, balance-sheet-risk, filing evidence, backtests, saved-position scenarios, and recent trend tags into transparent research views.

It is not a trading bot, financial advisor, or source of buy/sell/hold recommendations. Keep educational-use disclaimers visible at decision surfaces. Describe outputs as signals, evidence, risks, caveats, scenarios, or historical observations.

## Current state

- Product shell, dashboard, stock detail, methodology, auth, billing shell, saved stocks, and responsive layouts exist.
- Scaled universe artifacts currently cover 5,799 active stock detail files.
- The original public preview tickers remain: AAPL, MSFT, GOOGL, AMZN, JPM, JNJ, XOM, F, KO, INTC.
- Access tiers are centralized: signed out sees the original 10-stock preview; Google signed-in free users see the preview plus up to 3 potentially-undervalued and up to 3 Growth Spurt/emerging candidates; Pro users see the full 5,799-stock universe.
- ETL uses provider-aware Python modules for Yahoo chart prices and SEC company facts.
- Official scoring remains deterministic: value, quality, momentum, market risk, balance-sheet risk, momentum risk, confidence, and one mutually exclusive signal.
- Balance-sheet-aware scoring is official, but standalone balance-sheet artifacts remain intact.
- BM25 SEC filing retrieval is production-safe; local Ollama/RAG remains local/experimental or a production placeholder.
- Saved-stock 30/90-day projections use approved forecast output when available, then conservative historical scenario fallback, then unavailable. Customer-facing cards are normalized `HoldingOutcome` records, not ad-hoc UI math.
- Market-target scenarios are separate from ValueSignal projections. The schema/backend extension point remains, but market-target cards are hidden from the saved-portfolio UI until a legitimate provider is configured.
- Growth Spurt detector is display-only in v1. It does not alter official scoring or signals.

## Main architecture map

Frontend:

- `src/app/` - Next.js App Router pages and API routes.
- `src/features/dashboard/StockTable.tsx` - dashboard filters/table, including Growth Spurt filter.
- `src/app/stock/[ticker]/page.tsx` - stock detail page.
- `src/components/GrowthSpurtBadge.tsx` - compact badge and detail Recent Trend card.
- `src/components/BillingPlans.tsx` - Stripe Checkout buttons for monthly/yearly ValueSignal Pro plans.
- `src/components/HoldingOutcomeCard.tsx` - reusable saved-position outcome card/grid.
- `src/components/SavedStocksConsole.tsx` - user watchlist/portfolio/projection UI.
- `src/lib/etl.ts` - server-only generated JSON readers and shared artifact types.
- `src/lib/research.ts` - merges generated data with fallback stock fixtures.
- `src/lib/access-policy.ts` - public/free/pro stock visibility policy.
- `src/lib/billing-store.ts` - PostgreSQL subscription/event tables and entitlement lookup.
- `src/lib/stripe-server.ts` / `src/lib/stripe-signature.ts` - server-controlled Stripe REST calls and webhook signature verification.
- `src/types/stock.ts`, `src/types/forecast.ts`, `src/types/signal.ts` - frontend contracts.

Python/data pipeline:

- `scripts/run_etl.py` - main ETL boundary; writes dashboard/features/signals/stocks/ETL report.
- `scripts/features.py` - official feature engineering.
- `scripts/scoring.py` - official scoring and classification.
- `scripts/balance_sheet.py` - balance-sheet extraction and score/risk gates.
- `scripts/growth_spurt.py` - deterministic Growth Spurt formula and thresholds.
- `scripts/build_growth_spurt_artifacts.py` - repopulates Growth Spurt fields from existing generated price histories.
- `scripts/benchmark_growth_spurt.py` - point-in-time SPY benchmark for Growth Spurt.
- `scripts/build_search_index.py` - full/per-ticker BM25 index utilities and status synchronization.
- `scripts/build_search_index_batch.py` - resumable batch-aware BM25 population for scaled filing coverage.
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

## Billing / Stripe boundary

Stripe work is app-side and test-mode-first. Do not commit real Stripe keys. The live secret key previously pasted in chat should be rotated before real use.

Routes:

- `src/app/billing/page.tsx`
- `src/app/billing/success/page.tsx`
- `src/app/billing/cancel/page.tsx`
- `src/app/api/billing/checkout/route.ts`
- `src/app/api/billing/subscription/route.ts`
- `src/app/api/billing/webhook/route.ts`

Server-side subscription tables are created by `src/lib/billing-store.ts`:

- `user_subscription`
- `processed_stripe_event`

Access policy:

- `active` and `trialing` grant Pro.
- `canceled` grants Pro only until `currentPeriodEnd` when present and in the future.
- `past_due`, `paused`, `unpaid`, `incomplete`, `incomplete_expired`, and `none` do not grant Pro.
- Checkout success page is not proof of payment; verified webhooks are authoritative.

Required env placeholders:

```text
STRIPE_SECRET_KEY=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_VALUE_SIGNAL_PRODUCT_ID=
STRIPE_VALUE_SIGNAL_MONTHLY_PRICE_ID=
STRIPE_VALUE_SIGNAL_ANNUAL_PRICE_ID=
STRIPE_API_VERSION=2025-03-31.basil
NEXT_PUBLIC_APP_URL=
```

Use test-mode Stripe resources first. Do not create live resources, push, or deploy Stripe billing until explicitly approved.

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
- current generated counts: 5,799 attempted, 357 detected, 746 emerging, 4,548 not detected, 148 unavailable, 0 missing stock artifacts.
- compact dashboard/table cells render only `detected` and `emerging`; `not_detected` and `unavailable` intentionally render as empty cells instead of a "No tag" label.

Guardrail: do not blend Growth Spurt into official scoring without a later approved scoring-integration phase.

## Saved-position outcome cards

The saved-position UI shows two primary cards:

- `ValueSignal 30 Days`
- `ValueSignal 90 Days`

Each available card should show total gain/loss once as the headline, then gain/loss per share, estimated sell price, estimated position value, estimated return, scenario range, projection source, and a human-readable as-of date. Do not repeat total gain/loss as a body row.

Core formula:

```text
estimatedGainLossPerShare = estimatedSellPrice - currentPurchasePrice
estimatedTotalGainLoss = sharesHeld * estimatedGainLossPerShare
estimatedPositionValue = sharesHeld * estimatedSellPrice
```

For dollar-allocation mode, first calculate `impliedShares = dollarAllocation / currentPrice`, then use the same per-share formulas. Display that quantity as `Implied shares`, not `Shares held`. For share positions, display `Shares held`. Do not multiply a dollar allocation by the estimated sell price. Do not use "earnings" for a user's position outcome.

Unavailable ValueSignal cards should stay compact and use horizon-specific observation details, for example `Not enough historical data` plus `8 of 24 required observations` for 30 days or `8 of 12 required observations` for 90 days. Do not render unsupported market-target cards in the primary saved-portfolio UI.

Projection-source priority:

```text
approved non-baseline forecast model
  -> ValueSignal Conservative Historical Scenario
  -> unavailable with reason
```

Market-target scenarios can be calculated only from legitimate provider data with `targetMean`, `currentPriceAtCollection`, and a known `targetHorizonDays`. Current artifacts are `unsupported`; do not fabricate targets, scrape unofficial endpoints, or substitute ValueSignal estimates.

Personal 30/90-day scenario fields are user-entered and must remain collapsed/separate. They do not overwrite ValueSignal outcomes.

## Commands

Run from repository root.

Frontend:

```powershell
npm run dev
npm run test:brief
npm run test:billing
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
python scripts/build_search_index_batch.py --universe data/universe/universe.json --batch-size 25
python scripts/forecast/run_forecast_pipeline.py --summary
python scripts/pipeline_health.py
```

Use `--limit all` or omit `--limit` for an uncapped universe command only when that is intentional.

For broad/full-universe refreshes, do not run one monolithic live ETL. Use checkpointed raw fetches first, then merge:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL <CONTACT_EMAIL>"
$env:BALANCE_SHEET_SCORING_MODE="official"
$env:GROWTH_SPURT_MODE="display"
python scripts/pipeline/run_checkpointed_etl.py --universe data/universe/universe.json --limit all --batch-size 10 --max-workers 5 --fetch-only --skip-backtest
powershell -ExecutionPolicy Bypass -File scripts/pipeline/diagnose_checkpointed_etl.ps1
python scripts/pipeline/run_checkpointed_etl.py --universe data/universe/universe.json --limit all --batch-size 10 --merge-only --skip-backtest
python scripts/forecast/run_forecast_pipeline.py --summary --scaled-fast
python scripts/pipeline_health.py
```

Checkpoint files live under `data/checkpoints/etl_raw/` and are ignored by Git. The fetch writes/resumes after each ticker and also writes tiny `batch_*.status.json` sidecars for lightweight diagnostics. `--max-workers 5` fetches up to five tickers at once inside one coordinated process; do not start five independent scripts against the same checkpoint directory. Public `public/data/*.json` artifacts are not regenerated until the merge pass succeeds. SEC Company Facts payloads can be tens of MB for mega-caps, so full-universe fundamentals collection is bandwidth-heavy and may take many hours or days on a laptop. Future checkpoint fetches default to the normal 5-year price window; the first 5,799-stock run used shorter checkpointed price histories, so scaled-fast forecasts intentionally fall back to sparse historical scenarios where available.

Latest full-universe local result on 2026-07-22 UTC:

- Universe supported count: `6017`.
- Raw checkpoint fetch processed: `6017`; raw successes: `5802`; raw failures: `215`; local checkpoint store size: about `26.2 GB`.
- Merge/export published: `5799` stocks and forecasts; ETL failures/noncritical rows: `218`.
- Forecast scaled-fast scenarios: `5475` available, `321` insufficient data, `3` stale.
- `audit_features.py`, `audit_scoring.py`, `audit_search.py`, `forecast/audit_forecasts.py`, `pipeline_health.py`, `npm run test:brief`, `npm run test:billing`, `npm run typecheck`, and `npm run build` passed after the merge/billing checkpoint.
- `public/data/dashboard.json` is intentionally a lean dashboard-summary artifact; full per-ticker detail remains under `public/data/stocks/{TICKER}.json`, and official scoring detail remains in `signals.json`.
- Per-ticker artifact filenames use `scripts/artifact_paths.py` / `src/lib/artifact-paths.ts`; Windows-reserved tickers such as `CON` are stored as `_CON.json` while ticker IDs remain unchanged in JSON and URLs.
- BM25 is in per-ticker manifest mode. Current local coverage is 210 indexed tickers / 54,272 SEC chunks with 50 logged no-searchable-filing gaps and 5,757 unattempted supported universe rows. Continue coverage with `scripts/build_search_index_batch.py`; do not rebuild a monolithic search file.

Never commit `.env*`, secrets, tokens, real credentials, model files, caches, or local logs.

## Scheduled refresh

`.github/workflows/refresh-data.yml` runs weekdays at `25 23 * * 1-5` UTC and supports manual dispatch.

It currently builds a capped scaled universe, runs ETL, benchmarks Growth Spurt, runs a batch-aware BM25 filing-search increment, refreshes forecasts, runs audits, and publishes pipeline health. Scheduled runs are health checks only while the deployed dataset is full-universe; the artifact commit step is guarded to run on manual dispatch only. A pushed artifact commit triggers Vercel when automatic deployment is enabled. Important: do not remove this guard until an incremental/full-run automation design exists.

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
- Run `npm run test:brief`, `npm run test:billing`, `npm run typecheck`, and `npm run build`.
- Check mobile layout and long labels in dashboard/detail cards.

Saved outcomes:

- `src/lib/position-projections.ts` owns all ValueSignal calculations and preserves market-target schema/backend extension points.
- Dollar allocations first convert to `impliedShares = dollarAllocation / currentPrice`, then use per-share gain/loss math.
- Share positions use `shares * (estimatedFuturePrice - currentPrice)`.
- Valid zero-dollar change must render `$0.00`, not `Unavailable`.
- Missing/stale/currently unsupported market targets must not render as primary saved-portfolio cards; unavailable market-target scenario-source fields stay null for future compatibility.

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
