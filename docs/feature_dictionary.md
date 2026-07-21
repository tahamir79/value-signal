# ValueSignal feature dictionary

All features are computed using observations dated on or before each record's `asOf` date. Raw values remain visible beside winsorized values, cross-sectional percentiles, missingness flags, and range warnings. Winsorization is a documented normalization guard—not a deletion or silent correction of source data.

| Feature | Group | Formula | Minimum input | Valid range | Winsor bounds |
|---|---|---|---|---|---|
| `return_30d` | Momentum | adjusted close(t) / adjusted close(t-30 sessions) - 1 | 31 sessions | [-1, 5] | [-0.75, 2] |
| `return_90d` | Momentum | adjusted close(t) / adjusted close(t-90 sessions) - 1 | 91 sessions | [-1, 10] | [-0.85, 3] |
| `annualized_volatility` | Risk | sample stdev of daily log returns × sqrt(252) | 30 returns | [0, 5] | [0, 2] |
| `max_drawdown_1y` | Risk | minimum(price / running peak - 1) over 252 sessions | 1 session | [-1, 0] | [-1, 0] |
| `earnings_yield` | Value | latest annual net income / market capitalization | FY net income, shares, price | [-5, 5] | [-0.5, 0.5] |
| `sales_yield` | Value | latest annual revenue / market capitalization | FY revenue, shares, price | [0, 20] | [0, 5] |
| `liabilities_to_assets` | Risk | latest liabilities / latest assets | liabilities and assets | [0, 10] | [0, 2] |
| `revenue_growth` | Quality | latest FY revenue / previous FY revenue - 1 | two annual periods | [-5, 10] | [-1, 3] |
| `net_margin` | Quality | latest FY net income / latest FY revenue | annual income and revenue | [-10, 10] | [-2, 2] |
| `net_margin_trend` | Quality | latest FY margin - previous FY margin | two annual periods | [-10, 10] | [-1, 1] |

## Conventions

- Returns use adjusted close when the provider supplies it and raw close otherwise.
- Annual fundamentals select the latest-filed 10-K fact for each fiscal period, preserving deterministic restatement behavior.
- A missing input produces `null`; it is never converted to zero.
- Percentiles use average ranks for ties and return `0.5` for a one-company universe.
- Percentiles are ascending raw-feature ranks. Directionality belongs to the later scoring phase.
- `rangeWarnings` preserves plausible-but-suspicious observations for review.

## Display-only Growth Spurt detector v1

The Growth Spurt detector is not part of official ValueSignal scoring in v1. It is a separate recent-price-behavior artifact under `growthSpurt` in dashboard, summary, and stock-detail JSON.

| Feature | Formula | Window | Notes |
|---|---|---:|---|
| `return21d` | adjusted close(t) / adjusted close(t-21 sessions) - 1 | 21 | Recent confirmation |
| `return63d` | adjusted close(t) / adjusted close(t-63 sessions) - 1 | 63 | Primary direction |
| `trendSlope21d` | Theil-Sen slope of log prices | 21 | Robust confirmation trend |
| `trendSlope63d` | Theil-Sen slope of log prices | 63 | Primary rising-slash slope |
| `trendAnnualizedReturn63d` | exp(`trendSlope63d` x 252) - 1 | 63 | Direction magnitude, not a forecast |
| `trendFitR2_63d` | fit quality around robust trend line | 63 | Consistency check |
| `positiveWeekRatio63d` | positive 5-session chunks / valid chunks | 63 | Persistence check |
| `percentAboveTrendLine63d` | observations at or above fitted trend / observations | 63 | Shape check |
| `trendResidualVolatility63d` | stdev of robust-trend residuals | 63 | Zigzag/noise control |
| `maxDrawdown63d` | minimum price / running peak - 1 | 63 | Drawdown control |
| `downsideVolatility63d` | stdev of negative log returns | 63 | Downside-only volatility |
| `largestOneDayContribution63d` | largest absolute daily return / total absolute movement | 63 | Spike rejection |
| `excessReturnVsSpy21d` | `return21d` - SPY 21-session return | 21 | Market-relative confirmation |
| `excessReturnVsSpy63d` | `return63d` - SPY 63-session return | 63 | Required market benchmark |
| `trendAcceleration` | `trendSlope21d` - prior 42-session slope | 21 vs prior 42 | Optional confirmation boost |

Detection is `unavailable` when usable stock or SPY history is insufficient. Insufficient history is never converted to zero.
