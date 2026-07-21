# ValueSignal scoring specification v1.0.0

This is an explainable research baseline, not a prediction model. Every component is bounded to 0–100 and retains weighted contributions. Missing features are omitted and remaining weights are renormalized; missingness separately lowers confidence.

## Components

| Component | Inputs and weights | Direction |
|---|---|---|
| Value | earnings yield 60%, sales yield 40% | Higher percentile is stronger |
| Quality | net margin 45%, revenue growth 30%, margin trend 25% | Higher percentile is stronger |
| Momentum | 90-day return 60%, 30-day return 40% | Higher percentile is stronger |
| Market risk | drawdown severity 55%, volatility 45% | Higher score is more risk |
| Balance-sheet risk | liabilities/assets 100% | Higher percentile is more risk |

Drawdown percentiles are inverted because a more-negative drawdown has a lower raw percentile but represents greater risk. Momentum risk is `100 - momentum score`.

## Confidence

- High: at least 9 of 10 features available.
- Medium: 7–8 available.
- Low: 5–6 available.
- Insufficient: fewer than 5 available.

## Mutually exclusive classification priority

1. **Insufficient evidence:** confidence is insufficient.
2. **Value trap risk:** value ≥ 65 and balance-sheet risk ≥ 70.
3. **Momentum risk:** momentum risk ≥ 70.
4. **Potentially undervalued:** value ≥ 70, quality ≥ 50, market and balance-sheet risk both < 70.
5. **Quality watchlist:** quality ≥ 70 and balance-sheet risk < 70.
6. **Neutral:** all other combinations.

Risk rules precede positive labels so positive evidence cannot erase a material warning. Thresholds are hypotheses for later calibration and backtesting, not validated investment cutoffs.

## Display-only Growth Spurt detector

The Growth Spurt detector is intentionally outside official scoring in v1. It does not alter value, quality, momentum, market risk, balance-sheet risk, momentum risk, confidence, or the mutually exclusive signal classification.

Its `growthSpurtScore` is a separate 0-100 descriptive score for recent historical price behavior. The tag can coexist with any official signal, including risk labels. A detected tag should be read as "recent prices formed a persistent upward trend versus SPY with controlled drawdown," not as a buy/sell/hold recommendation or a price prediction.
