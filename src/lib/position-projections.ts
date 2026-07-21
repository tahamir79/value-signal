import type { AnalystTargetArtifact, ForecastArtifact, ForecastHorizon, HoldingOutcome, ProjectionSource } from "@/types/forecast";

export type ProjectionInput = {
  quantityType: "shares" | "dollar_amount";
  shares: number | null;
  dollarAmount: number | null;
  averageCostPerShare?: number | null;
};

export type HorizonProjection = {
  reason: string | null;
  source: ProjectionSource;
  sourceLabel: string;
  sourceDetail: string;
  lowerChange: number | null;
  baseChange: number | null;
  upperChange: number | null;
  lowerValue: number | null;
  baseValue: number | null;
  upperValue: number | null;
  lowerReturn: number | null;
  baseReturn: number | null;
  upperReturn: number | null;
  estimatedPrice: number | null;
  lowerEstimatedPrice: number | null;
  upperEstimatedPrice: number | null;
  sampleCount?: number | null;
};

export type PositionProjection = {
  currentPrice: number | null;
  marketDataAsOf: string | null;
  sharesHeld: number | null;
  currentPositionValue: number | null;
  costBasis: number | null;
  currentUnrealizedChange: number | null;
  reason: string | null;
  horizon30Day: HorizonProjection;
  horizon90Day: HorizonProjection;
  valueSignalOutcomes: [HoldingOutcome, HoldingOutcome];
  marketTargetOutcomes: [HoldingOutcome, HoldingOutcome];
  outcomes: [HoldingOutcome, HoldingOutcome, HoldingOutcome, HoldingOutcome];
};

type SelectedProjection = {
  source: ProjectionSource;
  sourceLabel: string;
  sourceDetail: string;
  reason: string | null;
  currentPrice: number | null;
  marketDataAsOf: string | null;
  horizon30Day: (ForecastHorizon & { sampleCount?: number }) | null;
  horizon90Day: (ForecastHorizon & { sampleCount?: number }) | null;
};

type PositionValueContext = {
  currentPositionValue: number | null;
  currentPrice: number | null;
  sharesHeld: number | null;
  reason: string | null;
};

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function validReturn(value: number | null | undefined) {
  return isFiniteNumber(value) && value > -1;
}

function validPrice(value: number | null | undefined) {
  return isFiniteNumber(value) && value > 0;
}

function isBaselineModel(name: string | null | undefined) {
  return name === "zero-return baseline" || name === "historical-mean baseline" || name === "market-return baseline";
}

function approvedForecastModel(forecast: ForecastArtifact) {
  return !isBaselineModel(forecast.model30Day?.name) && !isBaselineModel(forecast.model90Day?.name);
}

function completeHorizon(horizon: ForecastHorizon | null | undefined) {
  return Boolean(horizon && validReturn(horizon.returnEstimate) && validReturn(horizon.lowerReturn) && validReturn(horizon.upperReturn) && validPrice(horizon.estimatedPrice));
}

export function selectProjectionSource(forecast: ForecastArtifact | null | undefined): SelectedProjection {
  if (!forecast) {
    return { source: "unavailable", sourceLabel: "Projection unavailable", sourceDetail: "Forecast artifact has not been generated", reason: "Forecast artifact has not been generated", currentPrice: null, marketDataAsOf: null, horizon30Day: null, horizon90Day: null };
  }
  if (approvedForecastModel(forecast) && completeHorizon(forecast.horizon30Day) && completeHorizon(forecast.horizon90Day)) {
    return { source: "forecast_model", sourceLabel: "ValueSignal forecast model", sourceDetail: forecast.validationStatus === "validated" ? "Validated model output" : "Experimental model output", reason: forecast.displayProjectionReason ?? null, currentPrice: forecast.currentPrice, marketDataAsOf: forecast.marketDataAsOf, horizon30Day: forecast.horizon30Day, horizon90Day: forecast.horizon90Day };
  }
  const scenario = forecast.conservativeScenario;
  if (scenario?.status === "available" && validPrice(scenario.currentPrice) && completeHorizon(scenario.horizon30Day) && completeHorizon(scenario.horizon90Day)) {
    return { source: "conservative_historical_scenario", sourceLabel: "ValueSignal historical scenario", sourceDetail: "Conservative estimate based on historical price behavior", reason: forecast.displayProjectionReason ?? "Selected forecast model is a baseline benchmark; displaying the conservative historical scenario.", currentPrice: scenario.currentPrice, marketDataAsOf: scenario.marketDataAsOf, horizon30Day: scenario.horizon30Day, horizon90Day: scenario.horizon90Day };
  }
  return { source: "unavailable", sourceLabel: "Projection unavailable", sourceDetail: forecast.displayProjectionReason ?? scenario?.warnings?.[0] ?? "No approved model or sufficient historical scenario is available", reason: forecast.displayProjectionReason ?? scenario?.warnings?.[0] ?? "No approved model or sufficient historical scenario is available", currentPrice: validPrice(forecast.currentPrice) ? forecast.currentPrice : null, marketDataAsOf: forecast.marketDataAsOf, horizon30Day: null, horizon90Day: null };
}

function positionValueContext(input: ProjectionInput, currentPrice: number | null | undefined): PositionValueContext {
  const purchasePrice = validPrice(currentPrice) ? Number(currentPrice) : null;
  if (input.quantityType === "shares") {
    const sharesHeld = isFiniteNumber(input.shares) && input.shares > 0 ? input.shares : null;
    if (sharesHeld === null) {
      return { currentPositionValue: null, currentPrice: purchasePrice, sharesHeld: null, reason: "Position amount is required" };
    }
    if (purchasePrice === null) {
      return { currentPositionValue: null, currentPrice: null, sharesHeld, reason: "Current stock price unavailable" };
    }
    return {
      currentPositionValue: sharesHeld * purchasePrice,
      currentPrice: purchasePrice,
      sharesHeld,
      reason: null,
    };
  }
  const dollarAmount = isFiniteNumber(input.dollarAmount) && input.dollarAmount > 0 ? input.dollarAmount : null;
  if (dollarAmount === null) {
    return { currentPositionValue: null, currentPrice: purchasePrice, sharesHeld: null, reason: "Position amount is required" };
  }
  if (purchasePrice === null) {
    return { currentPositionValue: dollarAmount, currentPrice: null, sharesHeld: null, reason: "Current stock price unavailable" };
  }
  return {
    currentPositionValue: dollarAmount,
    currentPrice: purchasePrice,
    sharesHeld: dollarAmount / purchasePrice,
    reason: null,
  };
}

function costBasis(input: ProjectionInput) {
  if (input.quantityType !== "shares") return null;
  if (!isFiniteNumber(input.shares) || input.shares <= 0) return null;
  if (!isFiniteNumber(input.averageCostPerShare) || input.averageCostPerShare < 0) return null;
  return input.shares * input.averageCostPerShare;
}

function emptyHorizon(reason: string, source: SelectedProjection): HorizonProjection {
  return { reason, source: source.source, sourceLabel: source.sourceLabel, sourceDetail: source.sourceDetail, lowerChange: null, baseChange: null, upperChange: null, lowerValue: null, baseValue: null, upperValue: null, lowerReturn: null, baseReturn: null, upperReturn: null, estimatedPrice: null, lowerEstimatedPrice: null, upperEstimatedPrice: null, sampleCount: null };
}

function horizonProjection(input: ProjectionInput, baseValue: number | null, currentPrice: number | null, horizon: (ForecastHorizon & { sampleCount?: number }) | null | undefined, source: SelectedProjection): HorizonProjection {
  if (baseValue === null) {
    return emptyHorizon("Enter shares or a dollar amount", source);
  }
  if (!horizon) {
    return emptyHorizon(source.reason ?? "Projection source unavailable", source);
  }
  if (!validReturn(horizon.returnEstimate) || !validReturn(horizon.lowerReturn) || !validReturn(horizon.upperReturn)) {
    return emptyHorizon("Projection return unavailable", source);
  }
  const base = Number(horizon.returnEstimate);
  const lower = validReturn(horizon.lowerReturn) ? Number(horizon.lowerReturn) : base;
  const upper = validReturn(horizon.upperReturn) ? Number(horizon.upperReturn) : base;
  const basePrice = validPrice(horizon.estimatedPrice) ? Number(horizon.estimatedPrice) : validPrice(currentPrice) ? Number(currentPrice) * (1 + base) : null;
  const lowerPrice = validPrice(horizon.lowerEstimatedPrice) ? Number(horizon.lowerEstimatedPrice) : validPrice(currentPrice) ? Number(currentPrice) * (1 + lower) : null;
  const upperPrice = validPrice(horizon.upperEstimatedPrice) ? Number(horizon.upperEstimatedPrice) : validPrice(currentPrice) ? Number(currentPrice) * (1 + upper) : null;
  if (input.quantityType === "shares") {
    if (!isFiniteNumber(input.shares) || !validPrice(currentPrice) || !validPrice(basePrice) || !validPrice(lowerPrice) || !validPrice(upperPrice)) {
      return emptyHorizon("Share projection requires shares and a valid current price", source);
    }
    const shareCurrentPrice = Number(currentPrice);
    const shareBasePrice = Number(basePrice);
    const shareLowerPrice = Number(lowerPrice);
    const shareUpperPrice = Number(upperPrice);
    return {
      reason: null,
      source: source.source,
      sourceLabel: source.sourceLabel,
      sourceDetail: source.sourceDetail,
      lowerChange: input.shares * (shareLowerPrice - shareCurrentPrice),
      baseChange: input.shares * (shareBasePrice - shareCurrentPrice),
      upperChange: input.shares * (shareUpperPrice - shareCurrentPrice),
      lowerValue: input.shares * shareLowerPrice,
      baseValue: input.shares * shareBasePrice,
      upperValue: input.shares * shareUpperPrice,
      lowerReturn: lower,
      baseReturn: base,
      upperReturn: upper,
      estimatedPrice: basePrice,
      lowerEstimatedPrice: lowerPrice,
      upperEstimatedPrice: upperPrice,
      sampleCount: horizon.sampleCount ?? null,
    };
  }
  return {
    reason: null,
    source: source.source,
    sourceLabel: source.sourceLabel,
    sourceDetail: source.sourceDetail,
    lowerChange: baseValue * lower,
    baseChange: baseValue * base,
    upperChange: baseValue * upper,
    lowerValue: baseValue * (1 + lower),
    baseValue: baseValue * (1 + base),
    upperValue: baseValue * (1 + upper),
    lowerReturn: lower,
    baseReturn: base,
    upperReturn: upper,
    estimatedPrice: basePrice,
    lowerEstimatedPrice: lowerPrice,
    upperEstimatedPrice: upperPrice,
    sampleCount: horizon.sampleCount ?? null,
  };
}

function roundMoney(value: number | null): number | null {
  return isFiniteNumber(value) ? Math.round(value * 100) / 100 : null;
}

function unavailableOutcome(
  source: HoldingOutcome["source"],
  horizonDays: 30 | 90,
  label: string,
  reason: string,
  extras: Partial<HoldingOutcome> = {},
): HoldingOutcome {
  return {
    source,
    horizonDays,
    status: "unavailable",
    estimatedReturn: null,
    sharesHeld: extras.sharesHeld ?? null,
    currentPurchasePrice: extras.currentPurchasePrice ?? null,
    estimatedGainLossPerShare: null,
    estimatedGainLoss: null,
    estimatedSellPrice: null,
    estimatedPositionValue: null,
    asOf: extras.asOf ?? null,
    label,
    unavailableReason: reason,
    methodology: extras.methodology ?? null,
    sourceProvider: extras.sourceProvider ?? null,
    sourceHorizonDays: extras.sourceHorizonDays ?? null,
    consensusTarget: extras.consensusTarget ?? null,
    warnings: extras.warnings ?? [reason],
  };
}

function holdingValuesFromSellPrice(context: PositionValueContext, estimatedSellPrice: number | null | undefined): {
  gainLossPerShare: number | null;
  totalGainLoss: number | null;
  positionValue: number | null;
} {
  if (!validPrice(context.currentPrice) || !isFiniteNumber(context.sharesHeld) || context.sharesHeld <= 0 || !validPrice(estimatedSellPrice)) {
    return { gainLossPerShare: null, totalGainLoss: null, positionValue: null };
  }
  const gainLossPerShare = Number(estimatedSellPrice) - Number(context.currentPrice);
  return {
    gainLossPerShare,
    totalGainLoss: context.sharesHeld * gainLossPerShare,
    positionValue: context.sharesHeld * Number(estimatedSellPrice),
  };
}

function valuesignalOutcome(
  context: PositionValueContext,
  projection: HorizonProjection,
  horizonDays: 30 | 90,
  asOf: string | null,
): HoldingOutcome {
  const label = `ValueSignal ${horizonDays} Days`;
  if (context.currentPositionValue === null || context.currentPrice === null || context.sharesHeld === null) {
    return unavailableOutcome("valuesignal", horizonDays, label, context.reason ?? "Position amount is required", {
      asOf,
      sharesHeld: context.sharesHeld,
      currentPurchasePrice: context.currentPrice,
    });
  }
  if (projection.reason || projection.baseReturn === null || projection.baseChange === null || projection.baseValue === null) {
    return unavailableOutcome("valuesignal", horizonDays, label, projection.reason ?? "ValueSignal scenario unavailable", {
      asOf,
      methodology: projection.sourceLabel,
      sharesHeld: context.sharesHeld,
      currentPurchasePrice: context.currentPrice,
      warnings: [projection.reason ?? "ValueSignal scenario unavailable"],
    });
  }
  const holding = holdingValuesFromSellPrice(context, projection.estimatedPrice);
  if (holding.gainLossPerShare === null || holding.totalGainLoss === null || holding.positionValue === null) {
    return unavailableOutcome("valuesignal", horizonDays, label, "ValueSignal scenario unavailable", {
      asOf,
      methodology: projection.sourceLabel,
      sharesHeld: context.sharesHeld,
      currentPurchasePrice: context.currentPrice,
    });
  }
  const sourceStatus = projection.source === "unavailable" ? "unavailable" : "available";
  return {
    source: "valuesignal",
    horizonDays,
    status: sourceStatus,
    estimatedReturn: projection.baseReturn,
    sharesHeld: context.sharesHeld,
    currentPurchasePrice: context.currentPrice,
    estimatedGainLossPerShare: roundMoney(holding.gainLossPerShare),
    estimatedGainLoss: roundMoney(holding.totalGainLoss),
    estimatedSellPrice: projection.estimatedPrice,
    estimatedPositionValue: roundMoney(holding.positionValue),
    lowerReturn: projection.lowerReturn,
    upperReturn: projection.upperReturn,
    lowerEstimatedPositionValue: roundMoney(projection.lowerValue),
    upperEstimatedPositionValue: roundMoney(projection.upperValue),
    asOf,
    label,
    unavailableReason: null,
    methodology: projection.sourceLabel,
    sourceProvider: "ValueSignal",
    sourceHorizonDays: horizonDays,
    warnings: projection.sourceDetail ? [projection.sourceDetail] : [],
  };
}

function targetHorizonDays(target: AnalystTargetArtifact | null | undefined): number | null {
  const value = target?.targetHorizonDays ?? target?.horizonDays;
  return isFiniteNumber(value) && value > 0 ? Number(value) : null;
}

function targetHorizonLabel(target: AnalystTargetArtifact | null | undefined): string | null {
  return target?.targetHorizonLabel ?? target?.horizonLabel ?? null;
}

function analystTargetUnavailableReason(target: AnalystTargetArtifact | null | undefined): string | null {
  if (!target) return "Analyst target provider not configured";
  if (target.status === "unsupported") return "Analyst target provider not configured";
  if (target.status === "stale") return "Analyst target is stale";
  if (target.status === "horizon_unknown") return "Analyst target horizon not supplied";
  if (target.status === "insufficient_data") return "Analyst target unavailable for this stock";
  if (!validPrice(target.targetMean)) return "Analyst target unavailable for this stock";
  if (!validPrice(target.currentPriceAtCollection)) return "Current stock price unavailable";
  if (!targetHorizonDays(target)) return "Analyst target horizon not supplied";
  return null;
}

function scaledTargetReturn(targetMean: number, priceAtCollection: number, horizonDays: 30 | 90, targetHorizon: number): number | null {
  if (!validPrice(targetMean) || !validPrice(priceAtCollection) || !isFiniteNumber(targetHorizon) || targetHorizon <= 0) return null;
  const totalReturn = targetMean / priceAtCollection - 1;
  if (totalReturn <= -1) return null;
  return Math.pow(1 + totalReturn, horizonDays / targetHorizon) - 1;
}

function positionValueFromReturn(context: PositionValueContext, estimatedReturn: number): {
  estimatedGainLossPerShare: number | null;
  estimatedGainLoss: number | null;
  estimatedPositionValue: number | null;
  estimatedSellPrice: number | null;
} {
  if (!validPrice(context.currentPrice) || !isFiniteNumber(context.sharesHeld) || context.sharesHeld <= 0) {
    return { estimatedGainLossPerShare: null, estimatedGainLoss: null, estimatedPositionValue: null, estimatedSellPrice: null };
  }
  const currentPrice = Number(context.currentPrice);
  const estimatedSellPrice = currentPrice * (1 + estimatedReturn);
  const holding = holdingValuesFromSellPrice(context, estimatedSellPrice);
  return {
    estimatedGainLossPerShare: roundMoney(holding.gainLossPerShare),
    estimatedGainLoss: roundMoney(holding.totalGainLoss),
    estimatedPositionValue: roundMoney(holding.positionValue),
    estimatedSellPrice,
  };
}

function marketTargetOutcome(
  context: PositionValueContext,
  target: AnalystTargetArtifact | null | undefined,
  horizonDays: 30 | 90,
): HoldingOutcome {
  const label = `Market Target ${horizonDays} Days`;
  const sourceProvider = target?.provider ?? null;
  const sourceHorizonDays = targetHorizonDays(target);
  const asOf = target?.sourceAsOf ?? target?.collectedAt ?? null;
  const targetLabel = targetHorizonLabel(target);
  if (context.currentPositionValue === null || context.currentPrice === null || context.sharesHeld === null) {
    return unavailableOutcome("market_target", horizonDays, label, context.reason ?? "Position amount is required", {
      asOf,
      sourceProvider,
      sourceHorizonDays,
      sharesHeld: context.sharesHeld,
      currentPurchasePrice: context.currentPrice,
      consensusTarget: target?.targetMean ?? null,
    });
  }
  const reason = analystTargetUnavailableReason(target);
  if (reason || !target || !sourceHorizonDays || !validPrice(target.targetMean) || !validPrice(target.currentPriceAtCollection)) {
    return unavailableOutcome("market_target", horizonDays, label, reason ?? "Market-target scenario unavailable", {
      asOf,
      methodology: "Market-target implied scenario",
      sourceProvider,
      sourceHorizonDays,
      sharesHeld: context.sharesHeld,
      currentPurchasePrice: context.currentPrice,
      consensusTarget: target?.targetMean ?? null,
      warnings: target?.warnings?.length ? target.warnings : [reason ?? "Market-target scenario unavailable"],
    });
  }
  const estimatedReturn = scaledTargetReturn(Number(target.targetMean), Number(target.currentPriceAtCollection), horizonDays, sourceHorizonDays);
  if (!isFiniteNumber(estimatedReturn) || estimatedReturn <= -1) {
    return unavailableOutcome("market_target", horizonDays, label, "Market-target scenario unavailable", {
      asOf,
      methodology: "Market-target implied scenario",
      sourceProvider,
      sourceHorizonDays,
      sharesHeld: context.sharesHeld,
      currentPurchasePrice: context.currentPrice,
      consensusTarget: target.targetMean,
      warnings: target.warnings,
    });
  }
  const calculated = positionValueFromReturn(context, estimatedReturn);
  if (calculated.estimatedGainLossPerShare === null || calculated.estimatedGainLoss === null || calculated.estimatedPositionValue === null || calculated.estimatedSellPrice === null) {
    return unavailableOutcome("market_target", horizonDays, label, "Current stock price unavailable", {
      asOf,
      methodology: "Market-target implied scenario",
      sourceProvider,
      sourceHorizonDays,
      sharesHeld: context.sharesHeld,
      currentPurchasePrice: context.currentPrice,
      consensusTarget: target.targetMean,
    });
  }
  const targetReturnLow = validPrice(target.targetLow) ? scaledTargetReturn(Number(target.targetLow), Number(target.currentPriceAtCollection), horizonDays, sourceHorizonDays) : null;
  const targetReturnHigh = validPrice(target.targetHigh) ? scaledTargetReturn(Number(target.targetHigh), Number(target.currentPriceAtCollection), horizonDays, sourceHorizonDays) : null;
  return {
    source: "market_target",
    horizonDays,
    status: target.status === "stale" ? "stale" : "available",
    estimatedReturn,
    sharesHeld: context.sharesHeld,
    currentPurchasePrice: context.currentPrice,
    estimatedGainLossPerShare: calculated.estimatedGainLossPerShare,
    estimatedGainLoss: calculated.estimatedGainLoss,
    estimatedSellPrice: calculated.estimatedSellPrice,
    estimatedPositionValue: calculated.estimatedPositionValue,
    lowerReturn: targetReturnLow,
    upperReturn: targetReturnHigh,
    asOf,
    label,
    unavailableReason: null,
    methodology: targetLabel ? `Market-target implied scenario; target horizon ${targetLabel}` : "Market-target implied scenario",
    sourceProvider,
    sourceHorizonDays,
    consensusTarget: target.targetMean,
    warnings: [
      "Time-scaled from the external consensus target. This is not a direct analyst forecast for this period.",
      ...(target.warnings ?? []),
    ],
  };
}

export function calculatePositionProjection(input: ProjectionInput, forecast: ForecastArtifact | null | undefined): PositionProjection {
  const selected = selectProjectionSource(forecast);
  const context = positionValueContext(input, selected.currentPrice);
  const value = context.currentPositionValue;
  const basis = costBasis(input);
  const reason = context.reason;
  const horizon30Day = horizonProjection(input, value, selected.currentPrice, selected.horizon30Day, selected);
  const horizon90Day = horizonProjection(input, value, selected.currentPrice, selected.horizon90Day, selected);
  const valueSignalOutcomes: [HoldingOutcome, HoldingOutcome] = [
    valuesignalOutcome(context, horizon30Day, 30, selected.marketDataAsOf),
    valuesignalOutcome(context, horizon90Day, 90, selected.marketDataAsOf),
  ];
  const targetContext = positionValueContext(input, forecast?.currentPrice ?? selected.currentPrice);
  const marketTargetOutcomes: [HoldingOutcome, HoldingOutcome] = [
    marketTargetOutcome(targetContext, forecast?.analystTarget, 30),
    marketTargetOutcome(targetContext, forecast?.analystTarget, 90),
  ];
  return {
    currentPrice: selected.currentPrice,
    marketDataAsOf: selected.marketDataAsOf,
    sharesHeld: context.sharesHeld,
    currentPositionValue: value,
    costBasis: basis,
    currentUnrealizedChange: value !== null && basis !== null ? value - basis : null,
    reason,
    horizon30Day,
    horizon90Day,
    valueSignalOutcomes,
    marketTargetOutcomes,
    outcomes: [valueSignalOutcomes[0], valueSignalOutcomes[1], marketTargetOutcomes[0], marketTargetOutcomes[1]],
  };
}
