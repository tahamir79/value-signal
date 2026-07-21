import assert from "node:assert/strict";
import {describe,it} from "node:test";
import {calculatePositionProjection,selectProjectionSource} from "../src/lib/position-projections";
import type {ForecastArtifact} from "../src/types/forecast";

function artifact(overrides: Partial<ForecastArtifact> = {}): ForecastArtifact {
  return {
    schemaVersion: "1.0.0",
    ticker: "TEST",
    companyName: "Test Co",
    generatedAt: "2026-01-10T00:00:00+00:00",
    marketDataAsOf: "2026-01-09",
    currentPrice: 100,
    analystTarget: {
      ticker: "TEST",
      targetLow: null,
      targetMean: null,
      targetMedian: null,
      targetHigh: null,
      analystCount: null,
      currentPriceAtCollection: 100,
      impliedReturnToMean: null,
      horizonDays: null,
      horizonLabel: null,
      provider: "unsupported",
      sourceAsOf: null,
      collectedAt: "2026-01-10T00:00:00+00:00",
      status: "unsupported",
      warnings: [],
    },
    horizon30Day: {returnEstimate: 0, lowerReturn: -0.1, upperReturn: 0.1, estimatedPrice: 100, lowerEstimatedPrice: 90, upperEstimatedPrice: 110},
    horizon90Day: {returnEstimate: 0, lowerReturn: -0.2, upperReturn: 0.2, estimatedPrice: 100, lowerEstimatedPrice: 80, upperEstimatedPrice: 120},
    conservativeScenario: {
      methodology: "valuesignal_conservative_historical_scenario_v1",
      generatedAt: "2026-01-10T00:00:00+00:00",
      marketDataAsOf: "2026-01-09",
      currentPrice: 100,
      status: "available",
      warnings: [],
      horizon30Day: {returnEstimate: 0.02, lowerReturn: -0.04, upperReturn: 0.05, estimatedPrice: 102, lowerEstimatedPrice: 96, upperEstimatedPrice: 105, sampleCount: 30},
      horizon90Day: {returnEstimate: 0.04, lowerReturn: -0.08, upperReturn: 0.1, estimatedPrice: 104, lowerEstimatedPrice: 92, upperEstimatedPrice: 110, sampleCount: 18},
    },
    displayProjectionSource: "conservative_historical_scenario",
    displayProjectionReason: "baseline selected",
    model30Day: {name: "zero-return baseline", version: "1.0.0"},
    model90Day: {name: "zero-return baseline", version: "1.0.0"},
    validationStatus: "baseline",
    returnType: "price_return",
    warnings: [],
    ...overrides,
  };
}

describe("position projections",()=>{
  it("uses conservative scenario when selected model is only baseline",()=>{
    const selected=selectProjectionSource(artifact());
    assert.equal(selected.source,"conservative_historical_scenario");
    assert.equal(selected.horizon30Day?.returnEstimate,0.02);
  });

  it("calculates dollar allocation values from selected returns",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact());
    assert.equal(projection.horizon30Day.baseChange,20);
    assert.equal(projection.horizon30Day.baseValue,1020);
    assert.equal(projection.horizon90Day.baseChange,40);
  });

  it("calculates share values from future price deltas",()=>{
    const projection=calculatePositionProjection({quantityType:"shares",shares:10,dollarAmount:null},artifact());
    assert.equal(projection.currentPositionValue,1000);
    assert.equal(projection.horizon30Day.baseChange,20);
    assert.equal(projection.horizon30Day.baseValue,1020);
    assert.equal(projection.horizon90Day.upperValue,1100);
  });

  it("does not use analyst target or personal scenario as VS fallback",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({conservativeScenario:null,displayProjectionSource:"unavailable"}));
    assert.equal(projection.horizon30Day.source,"unavailable");
    assert.equal(projection.horizon30Day.baseValue,null);
  });
});
