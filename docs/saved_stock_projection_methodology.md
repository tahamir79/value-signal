# Saved-Stock and Position Projection Methodology

**Status:** research support only
**Last updated:** 2026-07-21 UTC
**Primary code:** `src/lib/position-projections.ts`, `src/components/SavedStocksConsole.tsx`

This document explains how ValueSignal turns a saved stock or position into the two customer-facing 30-day and 90-day ValueSignal outcome cards.

## 1. Conceptual separation

Saved-stock projections keep four concepts separate:

1. **ValueSignal selected model**: the auditable forecast model chosen by the forecast pipeline.
2. **ValueSignal conservative historical scenario**: deterministic fallback based on the stock's own prior price behavior.
3. **Personal scenario fields**: optional user-entered percentages for private planning.
4. **Analyst/market target**: preserved as backend schema/extension points, but hidden from the saved-position UI until a legitimate provider and documented target horizon are configured.

The UI must never use personal scenario fields or analyst-target placeholders as ValueSignal projections. It also must never describe position outcomes as "earnings"; use estimated gain/loss, estimated position value, and estimated sell price.

## 2. Source selection

Projection source priority:

```text
approved non-baseline forecast model
  -> conservative historical scenario
  -> unavailable with reason
```

Current artifacts select the zero-return baseline for both 30-day and 90-day model horizons. Because the selected model is a baseline, the UI displays the conservative historical scenario when available.

## 3. Holding gain/loss formula

Every saved-position outcome is calculated as a holding scenario, not company earnings or EPS.

Core terms:

```text
sharesHeld
currentPurchasePrice
estimatedSellPrice
estimatedGainLossPerShare = estimatedSellPrice - currentPurchasePrice
estimatedTotalGainLoss = sharesHeld * estimatedGainLossPerShare
estimatedPositionValue = sharesHeld * estimatedSellPrice
```

`currentPurchasePrice` is the current market price used by the saved-position view. The UI labels it as `Current price`.

For planned dollar allocation positions, first convert dollars into implied shares:

```text
impliedShares = dollarAllocation / currentPrice
```

Then use the same per-share formulas. Do not multiply a dollar allocation by an estimated sell price.

Example:

```text
currentPrice = 44.00
sharesHeld = 10
estimatedSellPrice = 45.25
estimatedGainLossPerShare = 45.25 - 44.00 = 1.25
estimatedTotalGainLoss = 10 * 1.25 = 12.50
estimatedPositionValue = 10 * 45.25 = 452.50
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

## 6. Analyst/market-target extension point

The market-target layer is separate from ValueSignal estimates. A market-target scenario can be calculated only when a real provider supplies:

- `targetMean`;
- `currentPriceAtCollection`;
- `targetHorizonDays`;
- non-stale provider status;
- display/redistribution permission.

The current fixture has no configured analyst target provider, so market-target cards are not displayed in the primary saved-portfolio interface. The `AnalystTargetArtifact` schema and `marketTargetOutcomes` remain in `src/lib/position-projections.ts` for a future provider-backed integration.

When valid provider data exists, the calculation is:

```text
totalTargetReturn = targetMean / currentPriceAtCollection - 1
marketImpliedReturn30 = (1 + totalTargetReturn)^(30 / targetHorizonDays) - 1
marketImpliedReturn90 = (1 + totalTargetReturn)^(90 / targetHorizonDays) - 1
```

This would be labeled as a market-implied scenario, not an analyst 30-day or 90-day forecast. Do not scrape unofficial financial websites or convert targets with unknown horizons.

## 7. UI labels

Current saved-position cards:

- `ValueSignal 30 Days`;
- `ValueSignal 90 Days`.

Each card is normalized as a `HoldingOutcome` by `src/lib/position-projections.ts` before React renders it. The card shows:

- estimated total gain/loss once, as the headline;
- gain/loss per share;
- estimated sell price;
- estimated position value;
- estimated return;
- scenario range;
- projection source;
- human-readable as-of date;
- concise unavailable reason when needed.

The current reference area above the two cards shows position type, current price, current position value, allocation when the position is dollar-based, `Implied shares` for dollar allocations, `Shares held` for share positions, and market data as-of date. Current price is not repeated inside each outcome card.

When a ValueSignal horizon is unavailable because the historical scenario lacks observations, the card shows `Not enough historical data` plus the horizon-specific observation count, such as `8 of 24 required observations` or `8 of 12 required observations`. The 90-day card must never reuse the 30-day observation requirement.

Unsupported market-target outcomes are not rendered in the primary saved-portfolio UI. If a future provider is configured, `methodology`, `sourceProvider`, and `sourceHorizonDays` must remain `null` for unavailable outcomes; scenario-source language appears only after a valid target, provider, horizon, and implied scenario exist.

Internal model-status area is collapsed under `Forecast methodology`:

- selected ValueSignal model names;
- zero-return baseline status;
- displayed projection source and sample count;
- personal scenario values.

Personal scenario inputs are labeled:

- Personal 30-Day Scenario %;
- Personal 90-Day Scenario %.

Helper text:

> Optional percentages entered by you. They do not change ValueSignal estimates.

## 8. Layout and overflow fix

The saved-stock overflow bug came from nested grids with fixed minimum widths and form controls that were not allowed to shrink inside the right-side pane.

Fixes live in `src/app/globals.css`:

- `min-width: 0` on grid/flex children;
- `box-sizing: border-box`;
- `width: 100%` and `max-width: 100%` on inputs/selects;
- safer `minmax(0, ...)` grid columns;
- responsive wrapping at desktop/tablet/mobile widths;
- `overflow-wrap: anywhere` for long text.

This fixes the cause rather than hiding horizontal overflow.

## 9. Validation

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
- zero-return outcomes remain available and display `$0.00`;
- negative returns show estimated losses;
- approved non-baseline models outrank conservative scenarios;
- analyst-target schema and backend outcomes stay backward compatible for future provider integration;
- market-target cards are absent from the primary saved-portfolio UI;
- analyst target not used as fallback;
- personal scenario not used as fallback.
