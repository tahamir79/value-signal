export type ForecastHorizon = {
  returnEstimate: number | null;
  lowerReturn: number | null;
  upperReturn: number | null;
  estimatedPrice: number | null;
  lowerEstimatedPrice: number | null;
  upperEstimatedPrice: number | null;
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
  model30Day: ForecastModelSummary;
  model90Day: ForecastModelSummary;
  validationStatus: "validated" | "experimental" | "insufficient_data" | "stale";
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
