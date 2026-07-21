# Saved-Stock and Position Projection Methodology

**Status:** research support only
**Last updated:** 2026-07-21 UTC
**Primary code:** `src/lib/position-projections.ts`, `src/components/SavedStocksConsole.tsx`

This document explains how ValueSignal turns a saved stock or position into 30-day and 90-day display cards.

## 1. Conceptual separation

Saved-stock projections keep four concepts separate:

1. **ValueSignal selected model**: the auditable forecast model chosen by the forecast pipeline.
2. **ValueSignal conservative historical scenario**: deterministic fallback based on the stock's own prior price behavior.
3. **Personal scenario fields**: optional user-entered percentages for private planning.
4. **Analyst/market target**: unsupported until a legitimate provider is added.

The UI must never use personal scenario fields or analyst-target placeholders as ValueSignal projections.

## 2. Source selection

Projection source priority:

```text
approved non-baseline forecast model
  -> conservative historical scenario
  -> unavailable with reason
```

Current artifacts select the zero-return baseline for both 30-day and 90-day model horizons. Because the selected model is a baseline, the UI displays the conservative historical scenario when available.

## 3. Dollar-allocation positions

For planned dollar allocation positions:

```text
currentPositionValue = dollarAmount
estimatedChange = currentPositionValue * returnEstimate
estimatedValue = currentPositionValue + estimatedChange
```

The same formula is applied to lower/base/upper returns.

Example:

```text
dollarAmount = 1,000
returnEstimate = 2%
estimatedChange = 20
estimatedValue = 1,020
```

## 4. Share positions

For share-based positions:

```text
currentPositionValue = shares * currentPrice
estimatedChange = shares * (estimatedFuturePrice - currentPrice)
estimatedValue = shares * estimatedFuturePrice
```

Do not calculate:

```text
shares * returnEstimate
```

That mixes share count and percentage return and produces a meaningless dollar number.

## 5. Future stock price

For a selected return source:

```text
estimatedFuturePrice = currentPrice * (1 + returnEstimate)
lowerEstimatedFuturePrice = currentPrice * (1 + lowerReturn)
upperEstimatedFuturePrice = currentPrice * (1 + upperReturn)
```

These prices are scenario outputs, not price targets or guarantees.

## 6. UI labels

Current saved-position cards:

- VS 30-day change;
- VS 30-day value;
- VS 90-day change;
- VS 90-day value.

Source labels:

- `ValueSignal forecast model`;
- `ValueSignal historical scenario`;
- `Projection unavailable`.

Model-status area:

- ValueSignal 30-day model;
- ValueSignal 90-day model;
- Displayed projection;
- Analyst consensus target.

Personal scenario inputs are labeled:

- Personal 30-day scenario %;
- Personal 90-day scenario %.

Helper text:

> Optional percentages entered by you. They do not change the ValueSignal estimate.

## 7. Layout and overflow fix

The saved-stock overflow bug came from nested grids with fixed minimum widths and form controls that were not allowed to shrink inside the right-side pane.

Fixes live in `src/app/globals.css`:

- `min-width: 0` on grid/flex children;
- `box-sizing: border-box`;
- `width: 100%` and `max-width: 100%` on inputs/selects;
- safer `minmax(0, ...)` grid columns;
- responsive wrapping at desktop/tablet/mobile widths;
- `overflow-wrap: anywhere` for long text.

This fixes the cause rather than hiding horizontal overflow.

## 8. Validation

Core tests:

```powershell
npm run test:brief
npm run typecheck
npm run build
```

Projection test coverage includes:

- conservative scenario selected when selected models are baseline;
- dollar allocation math;
- share-position math from future price deltas;
- analyst target not used as fallback;
- personal scenario not used as fallback.
