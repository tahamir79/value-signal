import type { SignalId } from "./signal";
export type ScoreSet = { value: number | null; quality: number | null; momentum: number | null; marketRisk?: number | null; balanceSheetRisk: number | null };
export type StockRecord = {
  ticker: string; companyName: string; sector: string; exchange: "NASDAQ" | "NYSE";
  price: number; dailyChangePercent: number; marketCapBillions: number;
  signal: SignalId; confidence: "High" | "Medium" | "Low" | "Insufficient"; scores: ScoreSet;
  summary: string; supportingEvidence: string[]; weakeningEvidence: string[]; asOf: string;
};
