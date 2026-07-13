# ValueSignal

ValueSignal is a transparent public-company research product. It organizes valuation, quality, momentum, and risk evidence into cautious research signals without presenting financial advice or buy/sell recommendations.

## Phase 01

This version contains the public product shell:

- Landing page and six-signal taxonomy
- Research dashboard with ten typed placeholder records
- Static stock-detail pages with evidence and risk breakdowns
- Methodology and limitations page
- Reusable educational-use disclaimer
- Responsive layouts for mobile and desktop

All displayed company observations are fixtures. Live data, calculated features, and scoring pipelines are intentionally deferred to later phases.

## Phase 02 ETL

The Python pipeline collects daily OHLCV prices through a swappable provider and normalized company facts from the SEC. It emits `public/data/dashboard.json` and `public/data/etl_report.json`; the dashboard automatically uses successful live observations and falls back to Phase 01 fixtures per field.

Set an identifying SEC user agent containing a monitored email, then run:

```bash
$env:VS_USER_AGENT="ValueSignal research ETL your-email@example.com"
python scripts/run_etl.py
python -m unittest discover -s tests -v
```

The scheduled GitHub workflow requires a repository secret named `VS_CONTACT_EMAIL`. It runs after U.S. market close on weekdays, commits changed artifacts, and thereby triggers the connected Vercel deployment.

## Phase 03 features

The same ETL run now writes `public/data/features.json`. Each company record includes raw features, documented winsorized values, contemporaneous-universe percentile ranks, explicit missingness flags, and range warnings. Formula definitions and valid ranges live in `docs/feature_dictionary.md`; feature calculations remain independent from the later scoring engine.

Run `python scripts/audit_features.py` to verify price ordering, the sqrt(252) annualization factor, denominator signs, and ticker-level outlier lineage. The scheduled workflow runs this audit before publishing refreshed data.

## Phase 04 scoring

`scripts/scoring.py` converts feature percentiles into bounded value, quality, momentum, market-risk, and balance-sheet-risk scores. Missing inputs renormalize component weights while lowering confidence. The six-label classifier, reason codes, explanations, and weighted contributions are exported to `public/data/signals.json` and rendered by the website. See `docs/scoring_specification.md` for weights and exact classification boundaries.

Run `python scripts/audit_scoring.py` to print weighted component scores, verify bounds and deterministic labels, and execute 20 ±20% weight-sensitivity scenarios.

## Phase 05 research interface

The dashboard now provides research KPIs, keyboard-accessible search/filter controls, and sortable score columns. Company pages render labeled adjusted-close history, score contributions, evidence coverage, reason codes, and plain-language summaries. Typed loaders degrade to fixtures or explicit empty states when generated artifacts are missing, partial, or stale.

## Phase 06 backtesting lab

The ETL now requests five years of prices, reconstructs monthly point-in-time feature and signal snapshots using SEC filing dates, and compares 30/60/90-session outcomes with date-aligned SPY returns. The `/backtest` route reports cohorts, confidence intervals, sample counts, adverse drawdowns, and bias limitations. See `docs/backtesting_protocol.md`.

## Phase 07 SEC filing retrieval (schema 3)

The scheduled pipeline fetches recent 10-K/10-Q documents, removes filing noise, detects canonical Part/Item sections, and creates stable metadata-rich chunks that never cross item boundaries. It builds a tokenized inverted index, ranks cited passages with BM25, and deterministically diversifies near-duplicate results. Stock pages expose inspectable section and offset metadata while keeping source evidence separate from quantitative analysis. See `docs/retrieval_specification.md`.

## Phase 08 deterministic analyst briefs

Stock pages generate cautious briefs from signal labels, validated scores, sample-sized backtest context, and cited SEC passages. Every claim retains a source reference; absent inputs are disclosed. Briefs support Markdown copy and print-only review. See `docs/brief_specification.md`.

## Optional local Ollama RAG

The local-only RAG layer combines the schema-3 SEC corpus, BM25, cached `nomic-embed-text` vectors, and `llama3.2:3b` synthesis. It explains existing signals with cited filing evidence and degrades visibly to BM25 when semantic retrieval is unavailable. It is not required by Vercel. See `docs/rag_specification.md`.

## Authentication

ValueSignal includes Better Auth scaffolding for Google sign-in backed by PostgreSQL. Public research pages remain open; auth prepares protected future AI/RAG features.

Required environment variables:

```bash
BETTER_AUTH_SECRET=
BETTER_AUTH_URL=
NEXT_PUBLIC_BETTER_AUTH_URL=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
DATABASE_URL=
```

Google OAuth callback URLs should point to `/api/auth/callback/google` for local and production domains.

## Scaling phase: broad universe foundation

The scaling path is a separate data-engineering phase. It starts with staged universe construction instead of blindly downloading every ticker. The current foundation supports `starter`, `watchlist`, `sp500_or_largecap`, `sec_listed_core`, `sec_listed_all`, and `custom` modes, preserves CIK/ticker/name/exchange fields, marks unsupported securities, and writes restartable run reports.

SEC requests must use a clear `VS_USER_AGENT` with a monitored contact email. The default SEC client is cached, retrying, and throttled conservatively at 5 requests per second or slower.

Example commands:

```bash
python scripts/universe/build_universe.py --mode starter
python scripts/universe/build_universe.py --mode sec_listed_core --limit 50
python scripts/pipeline/run_scaled_pipeline.py --mode starter
python scripts/pipeline/run_scaled_pipeline.py --mode sec_listed_core --limit 250 --resume
python scripts/filings/ingest_filings.py --universe data/universe/universe.json --forms 10-K 10-Q --limit 25
python scripts/pipeline/run_scaled_pipeline.py --mode starter --limit 10 --ingest-filings
python scripts/audit_search.py
python scripts/scoring.py
npm run build
```

Generated local scaling artifacts are written under `data/`:

- `data/universe/universe.json`
- `data/universe/universe_manifest.json`
- `data/reports/pipeline_report.json`
- `data/reports/failures.json`
- `data/filings/filing_metadata.json`
- `data/cache/sec/filings/chunks/*.json`

Do not publish giant raw filing corpora to the frontend bundle. The online dashboard should use compact summary/scoring data, while filing evidence remains lazy-loaded per ticker.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. Run `npm run typecheck` and `npm run build` before deployment.

## Routes

- `/`
- `/dashboard`
- `/backtest`
- `/stock/[ticker]`
- `/methodology`
