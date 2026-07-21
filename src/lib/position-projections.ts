import type { ForecastArtifact, ForecastHorizon, ProjectionSource } from "@/types/forecast";

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
  currentPositionValue: number | null;
  costBasis: number | null;
  currentUnrealizedChange: number | null;
  reason: string | null;
  horizon30Day: HorizonProjection;
  horizon90Day: HorizonProjection;
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

function currentPositionValue(input: ProjectionInput, currentPrice: number | null | undefined) {
  if (input.quantityType === "dollar_amount") {
    return isFiniteNumber(input.dollarAmount) && input.dollarAmount > 0 ? input.dollarAmount : null;
  }
  if (!isFiniteNumber(input.shares) || input.shares <= 0) return null;
  if (!validPrice(currentPrice)) return null;
  return input.shares * Number(currentPrice);
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

export function calculatePositionProjection(input: ProjectionInput, forecast: ForecastArtifact | null | undefined): PositionProjection {
  const selected = selectProjectionSource(forecast);
  const value = currentPositionValue(input, selected.currentPrice);
  const basis = costBasis(input);
  const reason = value === null
    ? input.quantityType === "shares" && !selected.currentPrice
      ? "Current market price unavailable"
      : "Enter shares or a dollar amount"
    : null;
  return {
    currentPositionValue: value,
    costBasis: basis,
    currentUnrealizedChange: value !== null && basis !== null ? value - basis : null,
    reason,
    horizon30Day: horizonProjection(input, value, selected.currentPrice, selected.horizon30Day, selected),
    horizon90Day: horizonProjection(input, value, selected.currentPrice, selected.horizon90Day, selected),
  };
}
