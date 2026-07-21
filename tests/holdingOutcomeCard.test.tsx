import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { HoldingOutcomeGrid } from "../src/components/HoldingOutcomeCard";
import type { HoldingOutcome } from "../src/types/forecast";

const outcomes: HoldingOutcome[] = [
  {
    source: "valuesignal",
    horizonDays: 30,
    status: "available",
    estimatedReturn: 0.02,
    sharesHeld: 10,
    currentPurchasePrice: 100,
    estimatedGainLossPerShare: 2,
    estimatedGainLoss: 20,
    estimatedSellPrice: 102,
    estimatedPositionValue: 1020,
    lowerReturn: -0.03,
    upperReturn: 0.06,
    asOf: "2026-01-09",
    label: "ValueSignal 30 Days",
    methodology: "ValueSignal historical scenario",
    sourceProvider: "ValueSignal",
    sourceHorizonDays: 30,
    warnings: [],
  },
  {
    source: "valuesignal",
    horizonDays: 90,
    status: "available",
    estimatedReturn: 0.04,
    sharesHeld: 10,
    currentPurchasePrice: 100,
    estimatedGainLossPerShare: 4,
    estimatedGainLoss: 40,
    estimatedSellPrice: 104,
    estimatedPositionValue: 1040,
    asOf: "2026-01-09",
    label: "ValueSignal 90 Days",
    methodology: "ValueSignal historical scenario",
    sourceProvider: "ValueSignal",
    sourceHorizonDays: 90,
    warnings: [],
  },
  {
    source: "market_target",
    horizonDays: 30,
    status: "unavailable",
    estimatedReturn: null,
    sharesHeld: 10,
    currentPurchasePrice: 100,
    estimatedGainLossPerShare: null,
    estimatedGainLoss: null,
    estimatedSellPrice: null,
    estimatedPositionValue: null,
    asOf: null,
    label: "Market Target 30 Days",
    unavailableReason: "Analyst target provider not configured",
    methodology: "Market-target implied scenario",
    sourceProvider: "unsupported",
    sourceHorizonDays: null,
    consensusTarget: null,
    warnings: ["Analyst target provider not configured"],
  },
  {
    source: "market_target",
    horizonDays: 90,
    status: "unavailable",
    estimatedReturn: null,
    sharesHeld: 10,
    currentPurchasePrice: 100,
    estimatedGainLossPerShare: null,
    estimatedGainLoss: null,
    estimatedSellPrice: null,
    estimatedPositionValue: null,
    asOf: null,
    label: "Market Target 90 Days",
    unavailableReason: "Analyst target provider not configured",
    methodology: "Market-target implied scenario",
    sourceProvider: "unsupported",
    sourceHorizonDays: null,
    consensusTarget: null,
    warnings: ["Analyst target provider not configured"],
  },
];

test("HoldingOutcomeGrid renders four outcome cards with explicit unavailable reasons", () => {
  const html = renderToStaticMarkup(<HoldingOutcomeGrid outcomes={outcomes} />);
  assert.match(html, /ValueSignal 30 Days/);
  assert.match(html, /ValueSignal 90 Days/);
  assert.match(html, /Market Target 30 Days/);
  assert.match(html, /Market Target 90 Days/);
  assert.match(html, /Estimated gain\/loss per share/);
  assert.match(html, /Shares held/);
  assert.match(html, /Estimated total gain\/loss/);
  assert.match(html, /Estimated sell price/);
  assert.match(html, /Estimated position value/);
  assert.match(html, /Estimated return percentage/);
  assert.match(html, /Analyst target provider not configured/);
  assert.match(html, /Analyst target data or target horizon is not available/);
});
