import type { Metadata } from "next";
import { StockTable } from "@/features/dashboard/StockTable";
import { DataStatus } from "@/features/dashboard/DataStatus";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { getEtlData,getEtlReport } from "@/lib/etl";
import { getResearchStocks } from "@/lib/research";
export const metadata:Metadata={title:"Research dashboard"};
export default async function DashboardPage(){
  const [etl,report,records]=await Promise.all([getEtlData(),getEtlReport(),getResearchStocks()]);
  const covered=records.filter(stock=>stock.signal!=="insufficient-evidence").length;
  return <div className="page"><header className="page-head split"><div><p className="eyebrow">RESEARCH UNIVERSE / PHASE 04</p><h1>Company signals</h1><p>Live observations and transparent component scores produce cautious, deterministic research classifications.</p></div><div className="as-of"><span>DATA GENERATED</span><strong>{etl.generatedAt?new Date(etl.generatedAt).toLocaleDateString("en-US",{dateStyle:"medium",timeZone:"UTC"}):"NOT RUN"}</strong></div></header><Disclaimer/><DataStatus report={report}/><section className="kpi-row" aria-label="Dashboard summary"><article><span>Companies</span><strong>{records.length}</strong><small>Starter universe</small></article><article><span>Researchable</span><strong>{covered}</strong><small>Confidence gate passed</small></article><article><span>Live scores</span><strong>{records.length}</strong><small>Scoring specification v1</small></article><article><span>Data mode</span><strong>{etl.mode}</strong><small>{etl.mode==="live"?"Versioned pipeline output":"Placeholder observations"}</small></article></section><section className="dashboard-section"><div className="section-head"><div><p className="eyebrow">SCREENING TABLE</p><h2>Compare the evidence</h2></div><p>Select any company to inspect its score contributions, confidence, and risks.</p></div><StockTable records={records}/></section></div>
}
