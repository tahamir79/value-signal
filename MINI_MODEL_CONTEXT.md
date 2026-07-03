# ValueSignal Mini-Model Context

Use this briefing for small debugging, maintenance, and implementation tasks. If it conflicts with the repository, **the code, tests, and active workflow configuration are the source of truth**.

## Product intent

ValueSignal is a public-company research tool. It organizes valuation, quality, momentum, market-risk, and balance-sheet-risk evidence into transparent signals. It is cautious educational research support—not a trading bot, financial advice, or a source of buy/sell recommendations.

Keep the educational-use disclaimer visible at decision surfaces. Describe outputs as signals, evidence, risks, or research observations rather than recommendations.

## Current state

- **Phase 01 — Product shell:** landing page, dashboard, stock detail pages, methodology, typed fixtures, responsive layout, and disclaimer.
- **Phase 02 — ETL:** ten-company universe, Yahoo chart price provider, SEC Company Facts provider, normalization, derived fields, JSON exports, audit report, partial-failure isolation, and fixture tests.
- **Phase 03 — Features:** raw financial/market features, winsorization, universe percentile ranks, missingness, range warnings, and feature audit tooling.
- **Phase 04 — Scoring:** bounded component scores, missing-input weight renormalization, confidence, deterministic six-label classification, reason codes, explanations, contributions, and sensitivity audit.
- **Phase 05 — Research interface:** typed fallback loaders, research KPIs, search/sort/filters, labeled price charts, score decomposition, analyst summaries, and visible empty, partial, and stale states.

The current universe is AAPL, MSFT, GOOGL, AMZN, JPM, JNJ, XOM, F, KO, and INTC.

## Architecture map

### Frontend

- `src/app/` — Next.js App Router pages: `/`, `/dashboard`, `/methodology`, and `/stock/[ticker]`.
- `src/features/` — page-specific modules for the dashboard, stock detail, and disclaimer.
- `src/components/` — reusable presentation and layout components.
- `src/lib/etl.ts` — server-only readers for generated JSON.
- `src/lib/research.ts` — merges live ETL/scoring values into typed stock fixtures, with per-field fixture fallbacks.
- `src/types/` and `src/data/` — frontend types, signal definitions, and fallback stock records.

### Python research pipeline

- `scripts/run_etl.py` — pipeline entry point and per-ticker failure boundary.
- `scripts/build_universe.py` — ticker/CIK universe.
- `scripts/providers/` — swappable Yahoo price and SEC Company Facts providers plus HTTP utilities.
- `scripts/cleaning.py` — financial-fact normalization and latest-fact selection.
- `scripts/features.py` — derived fields, raw features, winsorization, percentiles, and validation metadata.
- `scripts/scoring.py` — component scoring, classification, explanations, and sensitivity scenarios.
- `scripts/export_json.py` — JSON writer.
- `scripts/audit_features.py` and `scripts/audit_scoring.py` — publish gates and diagnostic output.

### Specifications and tests

- `docs/feature_dictionary.md` — feature formulas, units, and valid ranges.
- `docs/scoring_specification.md` — weights, directionality, confidence, and classification boundaries.
- `tests/` — fixture-based unit coverage for cleaning, pipeline resilience, features, and scoring.
- `.github/workflows/refresh-data.yml` — scheduled and manual ETL workflow.

> **Do not use `frontend.md` for ValueSignal work.** It is an unrelated DamLogics design brief left in the repository and does not describe this product.

## Data flow

```text
Ticker/CIK universe
  -> Yahoo prices + SEC Company Facts
  -> normalization and latest facts
  -> derived fields and raw features
  -> winsorized values and universe percentiles
  -> component scores, confidence, and signal labels
  -> public/data/*.json
  -> Next.js server-side file readers
  -> dashboard and stock-detail pages
```

Generated artifacts:

- `public/data/dashboard.json` — security metadata, current derived values, facts, and price history.
- `public/data/features.json` — raw, winsorized, percentile, missingness, and warning fields.
- `public/data/signals.json` — scores, signal labels, confidence, reason codes, explanations, and contributions.
- `public/data/etl_report.json` — run status, row counts, durations, and per-ticker errors.

Treat all `public/data/*.json` files as **generated artifacts**. Change pipeline logic or fixtures and regenerate them; do not hand-maintain production values.

The site currently reads these JSON files during Next.js rendering/build. It is not a continuously querying browser application. Refreshed data becomes public after GitHub Actions commits changed artifacts and the connected Vercel project redeploys that commit.

## Commands

Run commands from the repository root.

### Frontend

```powershell
npm install
npm run dev
npm run typecheck
npm run build
npm run start
```

`npm run dev` serves the local site at `http://localhost:3000`. Use `npm run start` only after a successful production build.

### Python tests and audits

```powershell
python -m unittest discover -s tests -v
python scripts/audit_features.py
python scripts/audit_scoring.py
```

Audits read the existing files under `public/data/`; they do not fetch fresh data.

### Live ETL

The SEC requires an identifying User-Agent containing a contact email. Set it locally without committing it:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL <CONTACT_EMAIL>"
python scripts/run_etl.py
```

Useful scoped run:

```powershell
python scripts/run_etl.py --limit 1 --output .tmp/etl-check
```

Never put a real email address, token, or secret value in source, logs intended for publication, or this document.

## Scheduled refresh and deployment

The GitHub workflow supports manual dispatch and runs on weekdays with cron `25 23 * * 1-5`—**23:25 UTC**, not local time. It:

1. Checks out the repository and sets up Python.
2. builds `VS_USER_AGENT` from the repository secret `VS_CONTACT_EMAIL`.
3. Runs unit tests.
4. Runs the live ETL.
5. Runs feature and scoring audits.
6. Commits and pushes the four generated JSON artifacts only when they changed.

The workflow needs `contents: write`. A successful artifact push triggers Vercel only when that GitHub repository/branch is connected with automatic deployments enabled. If data does not change, the workflow creates no commit, so there may be no redeployment.

## Debugging runbook

### ETL/provider failures

- Confirm the command runs from the repository root and `scripts/run_etl.py` exists.
- Confirm `VS_USER_AGENT` is present and contains `@`; in GitHub, confirm `VS_CONTACT_EMAIL` exists without printing its value.
- Inspect HTTP status, response headers, timeout/retry behavior, and provider-specific error text.
- Check `scripts/build_universe.py` ticker-to-CIK mappings, including zero padding expected by SEC requests.
- Compare SEC units, forms, filing dates, fiscal years, and fiscal periods before selecting a fact.
- Inspect `public/data/etl_report.json` for per-ticker status, row counts, and errors.
- Verify one ticker exception remains inside the ticker boundary and does not abort the universe.
- Verify the intended output directory and all four expected artifacts.

### Feature calculations

- Run the unit tests before the audit.
- Run `python scripts/audit_features.py`.
- Verify price dates are ascending and contain no duplicates.
- Verify volatility uses daily log returns multiplied by `sqrt(252)`.
- Check that price, shares, assets, and revenue denominators are positive before division.
- Trace outliers from percentile/winsorized values back to ticker-level raw inputs and source rows.
- Treat range warnings as items requiring investigation, not values to silently clamp away.

### Scoring

- Read `docs/scoring_specification.md` before changing weights or thresholds.
- Run `python scripts/audit_scoring.py`.
- Verify component scores stay within 0–100 and equal their weighted contributions.
- Verify missing features renormalize available weights and reduce confidence.
- Verify the classifier returns only the six IDs defined in `src/types/signal.ts`.
- Verify identical scores/confidence produce deterministic labels.
- Review the ±20% weight-sensitivity scenarios after scoring changes.

### Schema/frontend integration

- Compare generated keys and nullability with `src/lib/etl.ts`, `src/types/stock.ts`, and `src/types/signal.ts`.
- Ensure ticker is the unique join key across dashboard, features, signals, and fixtures.
- Check schema versions and timestamps in every artifact.
- Confirm fixture fallbacks still work when a ticker or individual live field is missing.
- Run `npm run typecheck` and `npm run build`.
- Test `/dashboard`, `/methodology`, and at least one valid and invalid `/stock/[ticker]` route.
- Check keyboard navigation, focus visibility, semantic headings, narrow mobile layout, and disclaimer visibility.

## Engineering guardrails

- Preserve modular boundaries: providers, cleaning, features, scoring, exporting, UI modules, and audits should remain independently testable.
- Do not let a single ticker failure stop the ETL run; record it in the audit report.
- Avoid coupling provider response shapes directly to frontend types.
- Keep formulas and classification policy transparent, deterministic, and documented.
- Preserve nulls and missingness honestly; do not invent financial values.
- Do not silently change score weights, feature directionality, thresholds, or schema versions.
- Keep educational disclaimers and cautious language at decision surfaces.
- Never claim certainty, predict returns, or generate direct buy/sell recommendations.
- Never commit `.env` files, contact details, API credentials, repository secrets, or private data.
- Preserve unrelated user changes in a dirty worktree. Avoid destructive Git commands.

## Small-task workflow

1. Read this file, then inspect the specific implementation and tests involved.
2. State the intended change and assumptions briefly.
3. Make the smallest modular change that solves the task.
4. Run focused tests, then the relevant broader gate.
5. Do not regenerate live artifacts unless the task requires it and `VS_USER_AGENT` is configured.
6. Report results using the handoff format below.

## Task handoff template

```markdown
Outcome: <what now works or what was diagnosed>

Changed files:
- <path>: <purpose>

Commands/checks:
- `<command>` — PASS/FAIL and important result

Generated artifacts:
- Regenerated: yes/no
- Files: <paths or none>

Remaining risks or follow-ups:
- <specific item, or none>
```
