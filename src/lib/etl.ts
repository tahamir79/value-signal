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
