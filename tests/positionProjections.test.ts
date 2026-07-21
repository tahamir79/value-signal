import assert from "node:assert/strict";
import {describe,it} from "node:test";
import {calculatePositionProjection,selectProjectionSource} from "../src/lib/position-projections";
import type {AnalystTargetArtifact,ForecastArtifact} from "../src/types/forecast";

function target(overrides: Partial<AnalystTargetArtifact> = {}): AnalystTargetArtifact {
  return {
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
    targetHorizonDays: null,
    targetHorizonLabel: null,
    provider: "unsupported",
    sourceAsOf: null,
    collectedAt: "2026-01-10T00:00:00+00:00",
    status: "unsupported",
    warnings: [],
    ...overrides,
  };
}

function artifact(overrides: Partial<ForecastArtifact> = {}): ForecastArtifact {
  return {
    schemaVersion: "1.0.0",
    ticker: "TEST",
    companyName: "Test Co",
    generatedAt: "2026-01-10T00:00:00+00:00",
    marketDataAsOf: "2026-01-09",
    currentPrice: 100,
    analystTarget: target(),
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
    assert.equal(projection.sharesHeld,10);
    assert.equal(projection.horizon30Day.baseChange,20);
    assert.equal(projection.horizon30Day.baseValue,1020);
    assert.equal(projection.horizon90Day.baseChange,40);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLossPerShare,2);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLoss,20);
    assert.equal(projection.valueSignalOutcomes[0].estimatedPositionValue,1020);
    assert.equal(projection.valueSignalOutcomes[1].estimatedGainLoss,40);
  });

  it("calculates share values from future price deltas",()=>{
    const projection=calculatePositionProjection({quantityType:"shares",shares:10,dollarAmount:null},artifact());
    assert.equal(projection.sharesHeld,10);
    assert.equal(projection.currentPositionValue,1000);
    assert.equal(projection.horizon30Day.baseChange,20);
    assert.equal(projection.horizon30Day.baseValue,1020);
    assert.equal(projection.horizon90Day.upperValue,1100);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLossPerShare,2);
    assert.equal(projection.valueSignalOutcomes[1].estimatedSellPrice,104);
  });

  it("matches the holding gain formula for the 44 dollar example",()=>{
    const forecast=artifact({
      currentPrice:44,
      conservativeScenario:{
        methodology:"valuesignal_conservative_historical_scenario_v1",
        generatedAt:"2026-01-10T00:00:00+00:00",
        marketDataAsOf:"2026-01-09",
        currentPrice:44,
        status:"available",
        warnings:[],
        horizon30Day:{returnEstimate:45.25/44-1,lowerReturn:0,upperReturn:0.05,estimatedPrice:45.25,lowerEstimatedPrice:44,upperEstimatedPrice:46.2,sampleCount:30},
        horizon90Day:{returnEstimate:0.04,lowerReturn:-0.08,upperReturn:0.1,estimatedPrice:45.76,lowerEstimatedPrice:40.48,upperEstimatedPrice:48.4,sampleCount:18},
      },
    });
    const projection=calculatePositionProjection({quantityType:"shares",shares:10,dollarAmount:null},forecast);
    assert.equal(projection.currentPositionValue,440);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLossPerShare,1.25);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLoss,12.5);
    assert.equal(projection.valueSignalOutcomes[0].estimatedSellPrice,45.25);
    assert.equal(projection.valueSignalOutcomes[0].estimatedPositionValue,452.5);
  });

  it("converts dollar allocation into implied shares before calculating gain",()=>{
    const forecast=artifact({
      currentPrice:44,
      conservativeScenario:{
        methodology:"valuesignal_conservative_historical_scenario_v1",
        generatedAt:"2026-01-10T00:00:00+00:00",
        marketDataAsOf:"2026-01-09",
        currentPrice:44,
        status:"available",
        warnings:[],
        horizon30Day:{returnEstimate:45.25/44-1,lowerReturn:0,upperReturn:0.05,estimatedPrice:45.25,lowerEstimatedPrice:44,upperEstimatedPrice:46.2,sampleCount:30},
        horizon90Day:{returnEstimate:0.04,lowerReturn:-0.08,upperReturn:0.1,estimatedPrice:45.76,lowerEstimatedPrice:40.48,upperEstimatedPrice:48.4,sampleCount:18},
      },
    });
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:440},forecast);
    assert.equal(projection.sharesHeld,10);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLossPerShare,1.25);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLoss,12.5);
    assert.equal(projection.valueSignalOutcomes[0].estimatedPositionValue,452.5);
  });

  it("preserves valid zero-return outcomes",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({
      model30Day:{name:"ridge regression",version:"1.0.0"},
      model90Day:{name:"ridge regression",version:"1.0.0"},
      validationStatus:"validated",
      horizon30Day:{returnEstimate:0,lowerReturn:0,upperReturn:0,estimatedPrice:100,lowerEstimatedPrice:100,upperEstimatedPrice:100},
      horizon90Day:{returnEstimate:0,lowerReturn:0,upperReturn:0,estimatedPrice:100,lowerEstimatedPrice:100,upperEstimatedPrice:100},
    }));
    assert.equal(projection.valueSignalOutcomes[0].status,"available");
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLossPerShare,0);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLoss,0);
    assert.equal(projection.valueSignalOutcomes[0].estimatedPositionValue,1000);
  });

  it("handles negative ValueSignal returns as losses",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({
      conservativeScenario:{
        methodology:"valuesignal_conservative_historical_scenario_v1",
        generatedAt:"2026-01-10T00:00:00+00:00",
        marketDataAsOf:"2026-01-09",
        currentPrice:100,
        status:"available",
        warnings:[],
        horizon30Day:{returnEstimate:-0.03,lowerReturn:-0.07,upperReturn:0.01,estimatedPrice:97,lowerEstimatedPrice:93,upperEstimatedPrice:101,sampleCount:30},
        horizon90Day:{returnEstimate:-0.05,lowerReturn:-0.1,upperReturn:0.02,estimatedPrice:95,lowerEstimatedPrice:90,upperEstimatedPrice:102,sampleCount:18},
      },
    }));
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLossPerShare,-3);
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLoss,-30);
    assert.equal(projection.valueSignalOutcomes[1].estimatedPositionValue,950);
  });

  it("prioritizes approved non-baseline model outputs over conservative scenario",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({
      model30Day:{name:"ridge regression",version:"1.0.0"},
      model90Day:{name:"ridge regression",version:"1.0.0"},
      validationStatus:"validated",
      horizon30Day:{returnEstimate:0.06,lowerReturn:0.01,upperReturn:0.09,estimatedPrice:106,lowerEstimatedPrice:101,upperEstimatedPrice:109},
      horizon90Day:{returnEstimate:0.08,lowerReturn:0.02,upperReturn:0.12,estimatedPrice:108,lowerEstimatedPrice:102,upperEstimatedPrice:112},
    }));
    assert.equal(projection.valueSignalOutcomes[0].methodology,"ValueSignal forecast model");
    assert.equal(projection.valueSignalOutcomes[0].estimatedGainLoss,60);
  });

  it("does not use analyst target or personal scenario as VS fallback",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({conservativeScenario:null,displayProjectionSource:"unavailable"}));
    assert.equal(projection.horizon30Day.source,"unavailable");
    assert.equal(projection.horizon30Day.baseValue,null);
    assert.equal(projection.valueSignalOutcomes[0].status,"unavailable");
  });

  it("converts a known 365-day market target to 30-day and 90-day scenarios",()=>{
    const forecast=artifact({analystTarget:target({
      targetMean:121,
      targetLow:90,
      targetHigh:140,
      analystCount:12,
      targetHorizonDays:365,
      targetHorizonLabel:"12 months",
      provider:"fixture",
      sourceAsOf:"2026-01-09",
      status:"available",
    })});
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},forecast);
    const expected30=Math.pow(1.21,30/365)-1;
    const expected90=Math.pow(1.21,90/365)-1;
    assert.equal(projection.marketTargetOutcomes[0].status,"available");
    assert.ok(Math.abs((projection.marketTargetOutcomes[0].estimatedReturn ?? 0)-expected30)<1e-12);
    assert.ok(Math.abs((projection.marketTargetOutcomes[1].estimatedReturn ?? 0)-expected90)<1e-12);
    assert.equal(projection.marketTargetOutcomes[0].estimatedGainLossPerShare,1.58);
    assert.equal(projection.marketTargetOutcomes[0].sourceHorizonDays,365);
  });

  it("converts another documented market-target horizon",()=>{
    const projection=calculatePositionProjection({quantityType:"shares",shares:5,dollarAmount:null},artifact({analystTarget:target({
      targetMean:110,
      targetHorizonDays:180,
      provider:"fixture",
      sourceAsOf:"2026-01-09",
      status:"available",
    })}));
    const expected30Price=100*(1+(Math.pow(1.1,30/180)-1));
    assert.ok(Math.abs((projection.marketTargetOutcomes[0].estimatedSellPrice ?? 0)-expected30Price)<1e-12);
    assert.ok(Math.abs((projection.marketTargetOutcomes[0].estimatedGainLossPerShare ?? 0)-(expected30Price-100))<0.01);
    assert.ok((projection.marketTargetOutcomes[0].estimatedGainLoss ?? 0)>0);
  });

  it("handles target below current price as a market-target loss scenario",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({analystTarget:target({
      targetMean:80,
      targetHorizonDays:365,
      provider:"fixture",
      sourceAsOf:"2026-01-09",
      status:"available",
    })}));
    assert.equal(projection.marketTargetOutcomes[0].status,"available");
    assert.ok((projection.marketTargetOutcomes[0].estimatedReturn ?? 0)<0);
    assert.ok((projection.marketTargetOutcomes[0].estimatedGainLoss ?? 0)<0);
  });

  it("does not calculate market-target scenarios with unknown horizons",()=>{
    const projection=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({analystTarget:target({
      targetMean:120,
      provider:"fixture",
      status:"horizon_unknown",
    })}));
    assert.equal(projection.marketTargetOutcomes[0].status,"unavailable");
    assert.equal(projection.marketTargetOutcomes[0].unavailableReason,"Analyst target horizon not supplied");
  });

  it("keeps unsupported and stale market targets unavailable",()=>{
    const unsupported=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact());
    assert.equal(unsupported.marketTargetOutcomes[0].unavailableReason,"Analyst target provider not configured");
    const stale=calculatePositionProjection({quantityType:"dollar_amount",shares:null,dollarAmount:1000},artifact({analystTarget:target({
      targetMean:120,
      targetHorizonDays:365,
      provider:"fixture",
      status:"stale",
    })}));
    assert.equal(stale.marketTargetOutcomes[0].unavailableReason,"Analyst target is stale");
  });
});
