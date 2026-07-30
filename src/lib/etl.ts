import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { GrowthSpurtArtifact, GrowthSpurtStatus } from "@/types/stock";
import { tickerArtifactStem } from "@/lib/artifact-paths";

export type PriceBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adjusted_close?: number | null;
};

export type DerivedFields = {
  latestPrice: number | null;
  dailyChangePercent: number | null;
  marketCapBillions: number | null;
  liabilitiesToAssets?: number | null;
  latestRevenueBillions?: number | null;
  revenueGrowthPercent?: number | null;
  grossMarginPercent?: number | null;
  netMarginPercent?: number | null;
};

export type DashboardRecord = {
  security: { ticker: string; cik: string; company_name: string; exchange: string; sector: string };
  derived: DerivedFields;
  dataStatus?: DataStatus;
  latestFacts?: Record<string, unknown>;
  balanceSheet?: BalanceSheetSnapshot;
  balanceSheetMetrics?: Record<string, number | null>;
  balanceSheetScoringShadow?: BalanceSheetScoringOutput;
  growthSpurt?: GrowthSpurtArtifact | null;
  priceHistory?: PriceBar[];
};

export type DataStatus = {
  rawSecTraceable?: boolean;
  submissionsAvailable?: boolean;
  companyFactsAvailable?: boolean;
  recent10KAvailable?: boolean;
  recent10QAvailable?: boolean;
  filingsDownloaded?: boolean;
  filingsCleaned?: boolean;
  filingsChunked?: boolean;
  bm25Indexed?: boolean;
  balanceSheetAvailable?: boolean;
  balanceSheetPartial?: boolean;
  balanceSheetSource?: string | null;
  balanceSheetPeriodEnd?: string | null;
  balanceSheetWarnings?: string[];
  balanceSheetQualityScore?: number | null;
  balanceSheetRiskPenalty?: number | null;
  liquidityScore?: number | null;
  leverageScore?: number | null;
  solvencyScore?: number | null;
  triggeredBalanceSheetGates?: string[];
  scoringInputsAvailable?: boolean;
  scoringAvailable?: boolean;
  officialSignal?: string | null;
  insufficientEvidenceReason?: string | null;
  latestFilingDate?: string | null;
  latestScoringDate?: string | null;
  growthSpurtAvailable?: boolean;
  growthSpurtStatus?: GrowthSpurtStatus | null;
  growthSpurtScore?: number | null;
  growthSpurtBenchmarkPercentile?: number | null;
  growthSpurtMarketDataAsOf?: string | null;
  lastPipelineRun?: string | null;
};

export type BalanceSheetSnapshot = {
  ticker:string;cik:string;companyName:string;formType?:string|null;accession?:string|null;
  filingDate?:string|null;periodEndDate?:string|null;source?:string|null;missingFields?:string[];dataQualityWarnings?:string[];
  assets?:number|null;currentAssets?:number|null;cashAndEquivalents?:number|null;shortTermInvestments?:number|null;
  accountsReceivable?:number|null;inventory?:number|null;propertyPlantEquipmentNet?:number|null;goodwill?:number|null;
  intangibleAssets?:number|null;liabilities?:number|null;currentLiabilities?:number|null;accountsPayable?:number|null;
  shortTermDebt?:number|null;longTermDebt?:number|null;totalDebt?:number|null;stockholdersEquity?:number|null;retainedEarnings?:number|null;
};

export type BalanceSheetTargetComparison = {
  metric:string;value:number|null;status:"healthy"|"acceptable"|"caution"|"risk"|"severe_risk"|"unavailable";healthyRange:string;interpretation:string;weight:number;
};

export type BalanceSheetRiskGate = {name:string;severity:string;triggered:boolean;explanation:string;metrics:string[]};

export type BalanceSheetScoringOutput = {
  liquidityScore:number|null;leverageScore:number|null;solvencyScore:number|null;assetQualityScore:number|null;
  balanceSheetQualityScore:number|null;balanceSheetRiskPenalty:number|null;triggeredRiskGates:BalanceSheetRiskGate[];
  targetComparisons:BalanceSheetTargetComparison[];confidenceAdjustment:number;warnings:string[];
  experimentalSignalImpact?:{wouldChangeSignal:boolean;currentOfficialSignal:string;experimentalSignal?:string|null;reason?:string|null};
};

export type EtlData = {
  schemaVersion: string;
  generatedAt: string | null;
  mode: "live" | "fixture";
  records: DashboardRecord[];
  loadError?: string;
};

export type EtlReport = {
  status: "not_run" | "success" | "partial_success";
  runFinishedAt: string | null;
  requestedTickers?: number;
  successfulTickers: number;
  failedTickers: number;
  coverageCounts?: Record<string, number | string>;
  publicationMode?: "incremental_batch_merge" | string;
  fullUniversePublishedTickers?: number;
  batchState?: {
    schemaVersion?: string;
    universeFingerprint?: string;
    universeSize?: number;
    previousOffset?: number;
    nextOffset?: number;
    batchSize?: number;
    batchCount?: number;
    dailySweepSlots?: number;
    plannedDailyRefreshTickers?: number;
    selectedTickers?: string[];
    updatedAt?: string;
    lastRunStartedAt?: string;
    lastRunFinishedAt?: string;
    lastSuccessfulTickers?: number;
    lastFailedTickers?: number;
  };
  loadError?: string;
};

export type ScoreContribution = {
  feature: string;
  percentile: number;
  directedPercentile: number;
  weight: number;
  points: number;
};

export type SignalRecord = {
  ticker: string;
  asOf: string;
  signal: string;
  confidence: "High" | "Medium" | "Low" | "Insufficient";
  scores: { value: number | null; quality: number | null; momentum: number | null; marketRisk: number | null; balanceSheetRisk: number | null };
  components: Record<string, { score: number | null; coverage: number; contributions: ScoreContribution[] }>;
  reasonCodes: string[];
  explanations: string[];
  balanceSheetScoringMode?: "off" | "shadow" | "experimental" | "official";
  balanceSheetScoringShadow?: BalanceSheetScoringOutput;
  experimentalBalanceSheetAdjustedSignal?: {signal:string;previousOfficialSignal:string;changed:boolean;reasons:string[];triggeredGates:string[]};
  balanceSheetOfficialChange?: {previousOfficialSignal:string;newSignal:string;changed:boolean;triggeredGates:string[]};
};

export type SignalData = {
  schemaVersion: string;
  generatedAt: string | null;
  records: SignalRecord[];
  loadError?: string;
};

export type BacktestCohort = {
  signal:string; horizonSessions:number; marketRegime:string; sampleCount:number;
  meanForwardReturn:number; meanBenchmarkReturn:number; meanExcessReturn:number;
  excessReturnConfidenceInterval95:[number,number]|null; winRate:number; meanAdverseDrawdown:number;
};
export type BacktestData = {
  schemaVersion:string; generatedAt:string|null; status:"complete"|"insufficient_data";
  protocol:{benchmark:string;executionLagSessions:number;forwardHorizonsSessions:number[];snapshotFrequencySessions:number;confidenceLevel:number;pointInTimeRule:string};
  snapshotCount:number;evaluatedObservationCount:number;observations:Array<Record<string,string|number|null>>;cohorts:BacktestCohort[];
  biasAudit:{passed:boolean;rejectedForLeakage:number;rejectedForDateAlignment:number;overlappingWindows:number;missingExpectedSymbols:string[];notes:string[]};
  traceObservation:Record<string,string|number>|null;limitations:string[];loadError?:string;
};

async function read<T>(name: string): Promise<T> {
  return JSON.parse(await readFile(path.join(process.cwd(), "public", "data", name), "utf8")) as T;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : "Unknown data-loading error";
}

export async function getEtlData(): Promise<EtlData> {
  try {
    return await read<EtlData>("dashboard.json");
  } catch (error) {
    return { schemaVersion: "unavailable", generatedAt: null, mode: "fixture", records: [], loadError: message(error) };
  }
}

export async function getEtlReport(): Promise<EtlReport> {
  try {
    return await read<EtlReport>("etl_report.json");
  } catch (error) {
    return { status: "not_run", runFinishedAt: null, successfulTickers: 0, failedTickers: 0, loadError: message(error) };
  }
}

export async function getSignalData(): Promise<SignalData> {
  try {
    return await read<SignalData>("signals.json");
  } catch (error) {
    return { schemaVersion: "unavailable", generatedAt: null, records: [], loadError: message(error) };
  }
}

export async function getStockDetailData(ticker:string):Promise<DashboardRecord|undefined>{
  try{
    const payload=await read<{record:DashboardRecord}>(`stocks/${tickerArtifactStem(ticker)}.json`);
    return payload.record;
  }catch{
    return undefined;
  }
}

export async function getBacktestData():Promise<BacktestData>{
  try{return await read<BacktestData>("backtest_results.json")}
  catch(error){return {schemaVersion:"unavailable",generatedAt:null,status:"insufficient_data",protocol:{benchmark:"SPY",executionLagSessions:1,forwardHorizonsSessions:[30,60,90],snapshotFrequencySessions:21,confidenceLevel:.95,pointInTimeRule:"Unavailable"},snapshotCount:0,evaluatedObservationCount:0,observations:[],cohorts:[],biasAudit:{passed:false,rejectedForLeakage:0,rejectedForDateAlignment:0,overlappingWindows:0,missingExpectedSymbols:[],notes:["Backtest results could not be loaded."]},traceObservation:null,limitations:[],loadError:message(error)}}
}

export async function getResearchDataState() {
  const [dashboard, report, signals] = await Promise.all([getEtlData(), getEtlReport(), getSignalData()]);
  return {
    dashboard,
    report,
    signals,
    hasLoadError: Boolean(dashboard.loadError || report.loadError || signals.loadError),
    isPartial: report.status === "partial_success" || dashboard.records.length !== signals.records.length,
  };
}
