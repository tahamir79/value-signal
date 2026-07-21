export type ForecastHorizon = {
  returnEstimate: number | null;
  lowerReturn: number | null;
  upperReturn: number | null;
  estimatedPrice: number | null;
  lowerEstimatedPrice: number | null;
  upperEstimatedPrice: number | null;
};

export type ProjectionSource = "forecast_model" | "conservative_historical_scenario" | "unavailable";

export type ForecastValidationStatus = "baseline" | "experimental" | "validated" | "insufficient_data" | "stale";

export type ConservativeScenarioHorizon = ForecastHorizon & {
  sampleCount: number;
};

export type ConservativeScenario = {
  methodology: "valuesignal_conservative_historical_scenario_v1";
  generatedAt: string;
  marketDataAsOf: string;
  currentPrice: number | null;
  horizon30Day: ConservativeScenarioHorizon;
  horizon90Day: ConservativeScenarioHorizon;
  status: "available" | "insufficient_data" | "stale";
  warnings: string[];
};

export type ForecastModelSummary = {
  name: string;
  version: string;
  testMAE?: number | null;
  directionalAccuracy?: number | null;
};

export type AnalystTargetArtifact = {
  ticker: string;
  targetLow: number | null;
  targetMean: number | null;
  targetMedian: number | null;
  targetHigh: number | null;
  analystCount: number | null;
  currentPriceAtCollection: number | null;
  impliedReturnToMean: number | null;
  horizonDays: number | null;
  horizonLabel: string | null;
  provider: string;
  sourceAsOf: string | null;
  collectedAt: string;
  status: "available" | "stale" | "insufficient_data" | "unsupported";
  warnings: string[];
};

export type ForecastArtifact = {
  schemaVersion: string;
  ticker: string;
  companyName: string;
  generatedAt: string;
  marketDataAsOf: string;
  currentPrice: number;
  analystTarget: AnalystTargetArtifact;
  horizon30Day: ForecastHorizon;
  horizon90Day: ForecastHorizon;
  conservativeScenario?: ConservativeScenario | null;
  displayProjectionSource?: ProjectionSource;
  displayProjectionReason?: string | null;
  model30Day: ForecastModelSummary;
  model90Day: ForecastModelSummary;
  validationStatus: ForecastValidationStatus;
  returnType: "price_return" | "total_return";
  warnings: string[];
};

export type ForecastSummary = {
  schemaVersion: string;
  generatedAt: string;
  count: number;
  validationStatus: ForecastArtifact["validationStatus"];
  forecasts: ForecastArtifact[];
};
