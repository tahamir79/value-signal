# ValueSignal backtesting protocol v1.0.0

This protocol evaluates whether historical ValueSignal classifications were useful research screens. It does not claim that results are investable or predictive.

## Frozen protocol

- Benchmark: SPY adjusted close.
- Snapshot cadence: every 21 benchmark trading sessions after at least 252 sessions of price history.
- Point-in-time rule: a snapshot may use prices through the signal date and SEC facts whose `filed` date is on or before the signal date.
- Execution lag: enter on the first security trading session after the signal date.
- Outcomes: 30, 60, and 90 trading sessions after entry.
- Metrics: security return, benchmark return, excess return, excess-return win rate, and maximum adverse drawdown.
- Segments: signal label, horizon, and positive/non-positive benchmark regime.
- Uncertainty: report sample counts and descriptive 95% normal confidence intervals for mean excess return.

## Bias controls

Snapshots with a price-through, filing-availability, or general availability date after the signal date are rejected. Security entry and outcome dates must exist exactly in the benchmark series. Overlapping forward windows are counted and disclosed because they are not independent observations.

The audit includes one fully traceable observation. The fixture suite shifts a filing date beyond the signal date to prove that leakage is rejected.

## Known limitations

- The current ten-symbol universe is based on companies that exist today; delisted companies and historical index constituents are not yet available. Survivorship bias therefore remains.
- Transaction costs, bid/ask spreads, slippage, taxes, and portfolio construction are excluded.
- Adjusted prices handle common distribution/split effects supplied by the provider, but provider revisions can change results.
- Normal confidence intervals are descriptive and can be optimistic when windows overlap or samples are small.
- Statistical significance is not the same as economic significance.

Results must remain unavailable rather than substituting current signals when point-in-time history cannot be reconstructed.
