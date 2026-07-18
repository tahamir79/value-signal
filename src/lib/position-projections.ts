import type { ForecastArtifact, ForecastHorizon } from "@/types/forecast";

export type ProjectionInput = {
  quantityType: "shares" | "dollar_amount";
  shares: number | null;
  dollarAmount: number | null;
  averageCostPerShare?: number | null;
};

export type HorizonProjection = {
  reason: string | null;
  lowerChange: number | null;
  baseChange: number | null;
  upperChange: number | null;
  lowerValue: number | null;
  baseValue: number | null;
  upperValue: number | null;
};

export type PositionProjection = {
  currentPositionValue: number | null;
  costBasis: number | null;
  currentUnrealizedChange: number | null;
  reason: string | null;
  horizon30Day: HorizonProjection;
  horizon90Day: HorizonProjection;
};

export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function validReturn(value: number | null | undefined) {
  return isFiniteNumber(value) && value > -1;
}

function currentPositionValue(input: ProjectionInput, forecast: ForecastArtifact | null | undefined) {
  if (input.quantityType === "dollar_amount") {
    return isFiniteNumber(input.dollarAmount) && input.dollarAmount > 0 ? input.dollarAmount : null;
  }
  if (!isFiniteNumber(input.shares) || input.shares <= 0) return null;
  if (!forecast || !isFiniteNumber(forecast.currentPrice) || forecast.currentPrice <= 0) return null;
  return input.shares * forecast.currentPrice;
}

function costBasis(input: ProjectionInput) {
  if (input.quantityType !== "shares") return null;
  if (!isFiniteNumber(input.shares) || input.shares <= 0) return null;
  if (!isFiniteNumber(input.averageCostPerShare) || input.averageCostPerShare < 0) return null;
  return input.shares * input.averageCostPerShare;
}

function horizonProjection(baseValue: number | null, horizon: ForecastHorizon | null | undefined): HorizonProjection {
  if (baseValue === null) {
    return { reason: "Enter shares or a dollar amount", lowerChange: null, baseChange: null, upperChange: null, lowerValue: null, baseValue: null, upperValue: null };
  }
  if (!horizon) {
    return { reason: "Forecast artifact has not been generated", lowerChange: null, baseChange: null, upperChange: null, lowerValue: null, baseValue: null, upperValue: null };
  }
  if (!validReturn(horizon.returnEstimate)) {
    return { reason: "Model estimate unavailable", lowerChange: null, baseChange: null, upperChange: null, lowerValue: null, baseValue: null, upperValue: null };
  }
  const base = Number(horizon.returnEstimate);
  const lower = validReturn(horizon.lowerReturn) ? Number(horizon.lowerReturn) : base;
  const upper = validReturn(horizon.upperReturn) ? Number(horizon.upperReturn) : base;
  return {
    reason: null,
    lowerChange: baseValue * lower,
    baseChange: baseValue * base,
    upperChange: baseValue * upper,
    lowerValue: baseValue * (1 + lower),
    baseValue: baseValue * (1 + base),
    upperValue: baseValue * (1 + upper),
  };
}

export function calculatePositionProjection(input: ProjectionInput, forecast: ForecastArtifact | null | undefined): PositionProjection {
  const value = currentPositionValue(input, forecast);
  const basis = costBasis(input);
  const reason = value === null
    ? input.quantityType === "shares" && !forecast
      ? "Current market price unavailable"
      : "Enter shares or a dollar amount"
    : null;
  return {
    currentPositionValue: value,
    costBasis: basis,
    currentUnrealizedChange: value !== null && basis !== null ? value - basis : null,
    reason,
    horizon30Day: horizonProjection(value, forecast?.horizon30Day),
    horizon90Day: horizonProjection(value, forecast?.horizon90Day),
  };
}
