import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { GrowthSpurtBadge } from "../src/components/GrowthSpurtBadge";
import type { GrowthSpurtArtifact } from "../src/types/stock";

const baseArtifact: GrowthSpurtArtifact = {
  schemaVersion: "1.0.0",
  ticker: "AAPL",
  generatedAt: "2026-07-21T00:00:00+00:00",
  marketDataAsOf: "2026-07-20",
  status: "detected",
  growthSpurtScore: 78,
  primaryWindowSessions: 63,
  confirmationWindowSessions: 21,
  metrics: {
    return21d: 0.04,
    return63d: 0.142,
    trendSlope21d: 0.001,
    trendSlope63d: 0.002,
    trendAnnualizedReturn63d: 0.65,
    trendFitR2_63d: 0.72,
    positiveWeekRatio63d: 0.75,
    trendResidualVolatility63d: 0.01,
    maxDrawdown63d: -0.041,
    downsideVolatility63d: 0.005,
    excessReturnVsSpy21d: 0.02,
    excessReturnVsSpy63d: 0.058,
    trendAcceleration: 0.0002,
    largestOneDayContribution63d: 0.08,
    percentAboveTrendLine63d: 0.68,
  },
  scoreBreakdown: {
    directionScore: 80,
    consistencyScore: 72,
    relativeStrengthScore: 84,
    drawdownControlScore: 88,
    confirmationScore: 76,
  },
  benchmarkPercentile: 0.84,
  metricPercentiles: {},
  reasonCodes: ["GROWTH_SPURT_DETECTED"],
  warnings: [],
};

test("GrowthSpurtBadge renders detected status and disclosure", () => {
  const html = renderToStaticMarkup(<GrowthSpurtBadge artifact={baseArtifact} variant="detail" />);
  assert.match(html, /Growth spurt detected/);
  assert.match(html, /Score/);
  assert.match(html, /78\/100/);
  assert.match(html, /does not predict/);
});

test("GrowthSpurtBadge renders emerging without the green check wording", () => {
  const html = renderToStaticMarkup(<GrowthSpurtBadge artifact={{ ...baseArtifact, status: "emerging", growthSpurtScore: 61 }} />);
  assert.match(html, /Emerging/);
  assert.doesNotMatch(html, /✅ Growth spurt detected/);
});

test("GrowthSpurtBadge renders unavailable reason", () => {
  const html = renderToStaticMarkup(<GrowthSpurtBadge artifact={{ ...baseArtifact, status: "unavailable", growthSpurtScore: null, warnings: ["TREND_HISTORY_INSUFFICIENT"] }} variant="detail" />);
  assert.match(html, /Trend history unavailable/);
  assert.match(html, /trend history insufficient/);
});
