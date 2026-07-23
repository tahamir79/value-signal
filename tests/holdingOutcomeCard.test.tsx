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
    estimatedReturn: 0.01850904,
    sharesHeld: 0.0229990801,
    shareLabel: "Implied shares",
    currentPurchasePrice: 43.48,
    estimatedGainLossPerShare: 0.8,
    estimatedGainLoss: 0.02,
    estimatedSellPrice: 44.2848,
    estimatedPositionValue: 1.02,
    lowerReturn: -0.03,
    upperReturn: 0.06,
    asOf: "2026-07-20",
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
    estimatedReturn: -0.03,
    sharesHeld: 0.0229990801,
    shareLabel: "Implied shares",
    currentPurchasePrice: 43.48,
    estimatedGainLossPerShare: -1.3,
    estimatedGainLoss: -0.03,
    estimatedSellPrice: 42.18,
    estimatedPositionValue: 0.97,
    asOf: "2026-07-21T03:51:42.553875+00:00",
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
    sharesHeld: 0.0229990801,
    shareLabel: "Implied shares",
    currentPurchasePrice: 43.48,
    estimatedGainLossPerShare: null,
    estimatedGainLoss: null,
    estimatedSellPrice: null,
    estimatedPositionValue: null,
    asOf: null,
    label: "Market Target 30 Days",
    unavailableReason: "Analyst target data is not currently available.",
    unavailableDetail: null,
    methodology: null,
    sourceProvider: null,
    sourceHorizonDays: null,
    consensusTarget: null,
    warnings: ["Current project artifacts do not include analyst consensus target fields from a contracted market-data provider."],
  },
  {
    source: "market_target",
    horizonDays: 90,
    status: "unavailable",
    estimatedReturn: null,
    sharesHeld: 0.0229990801,
    shareLabel: "Implied shares",
    currentPurchasePrice: 43.48,
    estimatedGainLossPerShare: null,
    estimatedGainLoss: null,
    estimatedSellPrice: null,
    estimatedPositionValue: null,
    asOf: null,
    label: "Market Target 90 Days",
    unavailableReason: "Analyst target data is not currently available.",
    unavailableDetail: null,
    methodology: null,
    sourceProvider: null,
    sourceHorizonDays: null,
    consensusTarget: null,
    warnings: ["Current project artifacts do not include analyst consensus target fields from a contracted market-data provider."],
  },
];

test("HoldingOutcomeGrid renders only two ValueSignal outcome cards", () => {
  const html = renderToStaticMarkup(<HoldingOutcomeGrid outcomes={outcomes} />);
  const articleCount = (html.match(/<article/g) ?? []).length;
  assert.equal(articleCount, 2);
  assert.match(html, /ValueSignal 30 Days/);
  assert.match(html, /ValueSignal 90 Days/);
  assert.doesNotMatch(html, /Market Target 30 Days/);
  assert.doesNotMatch(html, /Market Target 90 Days/);
  assert.match(html, /Estimated total gain/);
  assert.match(html, /Estimated total loss/);
  assert.match(html, /Estimated return/);
  assert.match(html, /Estimated sell price/);
  assert.match(html, /Estimated position value/);
  assert.match(html, /Gain per share/);
  assert.match(html, /Loss per share/);
  assert.match(html, /Scenario range/);
  assert.match(html, /-3.00% to \+6.00%/);
  assert.match(html, /Projection source/);
  assert.match(html, /Historical scenario/);
  assert.match(html, /As of Jul 20, 2026/);
  assert.match(html, /As of Jul 21, 2026/);
  assert.doesNotMatch(html, /Analyst target data is not currently available/);
  assert.doesNotMatch(html, /Estimated total gain\/loss/);
  assert.doesNotMatch(html, /Provider: unsupported/);
  assert.doesNotMatch(html, /Target horizon: Unavailable/);
  assert.doesNotMatch(html, /2026-07-21T03:51:42/);
});

test("HoldingOutcomeGrid shows total gain only once per available card", () => {
  const html = renderToStaticMarkup(<HoldingOutcomeGrid outcomes={[outcomes[0]]} />);
  assert.equal((html.match(/Estimated total gain/g) ?? []).length, 1);
  assert.equal((html.match(/\+\$0\.02/g) ?? []).length, 1);
  assert.match(html, /Gain per share/);
  assert.doesNotMatch(html, /Estimated total gain\/loss/);
});

test("HoldingOutcomeGrid renders exact zero as no estimated change", () => {
  const zero: HoldingOutcome = {
    ...outcomes[0],
    estimatedReturn: 0,
    estimatedGainLossPerShare: 0,
    estimatedGainLoss: 0,
    estimatedSellPrice: 43.48,
    estimatedPositionValue: 1,
  };
  const html = renderToStaticMarkup(<HoldingOutcomeGrid outcomes={[zero]} />);
  assert.match(html, /\$0.00/);
  assert.match(html, /No estimated change/);
  assert.match(html, /Change per share/);
  assert.doesNotMatch(html, /Unavailable/);
});

test("HoldingOutcomeGrid renders compact horizon-specific unavailable ValueSignal cards", () => {
  const unavailable: HoldingOutcome[] = [
    {
      ...outcomes[0],
      status: "unavailable",
      estimatedReturn: null,
      estimatedGainLossPerShare: null,
      estimatedGainLoss: null,
      estimatedSellPrice: null,
      estimatedPositionValue: null,
      unavailableReason: "Not enough historical data",
      unavailableDetail: "8 of 24 required observations",
    },
    {
      ...outcomes[1],
      status: "unavailable",
      estimatedReturn: null,
      estimatedGainLossPerShare: null,
      estimatedGainLoss: null,
      estimatedSellPrice: null,
      estimatedPositionValue: null,
      unavailableReason: "Not enough historical data",
      unavailableDetail: "8 of 12 required observations",
    },
  ];
  const html = renderToStaticMarkup(<HoldingOutcomeGrid outcomes={unavailable} />);
  assert.match(html, /Not enough historical data/);
  assert.match(html, /8 of 24 required observations/);
  assert.match(html, /8 of 12 required observations/);
  assert.match(html, /As of Jul 20, 2026/);
  assert.match(html, /As of Jul 21, 2026/);
  assert.doesNotMatch(html, /30-day scenario/);
  assert.doesNotMatch(html, /Estimated sell price/);
  assert.doesNotMatch(html, /Gain per share/);
  assert.doesNotMatch(html, /Source:/);
});
