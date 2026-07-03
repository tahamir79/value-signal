import "server-only";
import { readFile } from "node:fs/promises";
import path from "node:path";

export type PriceBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adjusted_close?: number | null;
};

export type DashboardRecord = {
  security: { ticker: string; cik: string; company_name: string; exchange: string; sector: string };
  derived: { latestPrice: number | null; dailyChangePercent: number | null; marketCapBillions: number | null };
  priceHistory: PriceBar[];
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
  successfulTickers: number;
  failedTickers: number;
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
