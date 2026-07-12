import type { SignalId } from "./signal";
export type ScoreSet = { value: number | null; quality: number | null; momentum: number | null; marketRisk?: number | null; balanceSheetRisk: number | null };
export type StockRecord = {
  ticker: string; companyName: string; sector: string; exchange: string;
  price: number; dailyChangePercent: number; marketCapBillions: number;
  signal: SignalId; confidence: "High" | "Medium" | "Low" | "Insufficient"; scores: ScoreSet;
  summary: string; supportingEvidence: string[]; weakeningEvidence: string[]; asOf: string;
  dataStatus?: { scoringAvailable?: boolean; bm25Indexed?: boolean; latestFilingDate?: string | null; insufficientEvidenceReason?: string | null; balanceSheetAvailable?: boolean; balanceSheetPartial?: boolean; balanceSheetQualityScore?: number | null; balanceSheetRiskPenalty?: number | null; triggeredBalanceSheetGates?: string[] };
};
