# ValueSignal balance-sheet scoring v1.0.0

Balance-sheet scoring is an additive, auditable layer over the existing ValueSignal ETL. It uses SEC companyfacts data and does not require an LLM. The default mode is `BALANCE_SHEET_SCORING_MODE=shadow`, which computes balance-sheet context without changing official scores, confidence, reason codes, or signals.

## Modes

- `off`: do not apply balance-sheet scoring output.
- `shadow`: compute snapshots, metrics, target comparisons, risk gates, and experimental signal impact without changing official scoring.
- `experimental`: add a separate experimental balance-sheet-adjusted signal without overwriting official scoring.
- `official`: allow balance-sheet quality/risk to influence official quality, balance-sheet risk, confidence, and classification.

## Score direction

Existing ValueSignal risk scores use higher-is-riskier. The balance-sheet layer therefore exposes two explicit fields:

- `balanceSheetQualityScore`: higher means stronger liquidity/leverage/solvency/asset-quality evidence.
- `balanceSheetRiskPenalty`: higher means more balance-sheet risk and maps cleanly into the existing higher-is-riskier convention.

## Inputs

The extractor selects the latest 10-K/10-Q balance-sheet filing context from normalized SEC companyfacts. It prefers facts matching the selected accession and period end, records missing fields as `null`, and never fabricates values.

Core facts include assets, current assets, cash, investments, receivables, inventory, PP&E, goodwill, intangibles, liabilities, current liabilities, payables, short-term debt, long-term debt, equity, retained earnings, and shares outstanding when available.

## Metrics and gates

Derived metrics include current ratio, quick ratio, cash ratio, working capital, debt/equity, debt/assets, equity ratio, cash/debt, net debt, goodwill and intangibles/assets, short-term debt share, book value, book value/share, and price/book when inputs exist.

Target bands are centralized in `data/scoring/balance_sheet_targets.json`. Current default risk gates are:

- Liquidity Risk Gate
- Severe Liquidity Risk Gate
- High Leverage Gate
- Severe Leverage Gate
- Negative Equity Gate
- Debt Maturity Pressure Gate
- Asset Quality Warning Gate
- Balance Sheet Incomplete Gate

## Official scoring behavior

In `shadow` and `experimental` modes, official scoring remains v1-compatible. In `official` mode only, the system may blend balance-sheet risk penalty into the existing balance-sheet risk score, modestly blend balance-sheet quality into quality score, adjust confidence, and route strong value plus severe balance-sheet weakness toward value-trap risk.

All changes should be reviewed with `scripts/compare_scoring_outputs.py` against `data/reports/scoring_baseline_before_balance_sheet_integration.json`.
