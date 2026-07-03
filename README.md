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

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. Run `npm run typecheck` and `npm run build` before deployment.

## Routes

- `/`
- `/dashboard`
- `/stock/[ticker]`
- `/methodology`
