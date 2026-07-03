import type { Metadata } from "next";
import { StockTable } from "@/features/dashboard/StockTable";
import { DataStatus } from "@/features/dashboard/DataStatus";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { stocks } from "@/data/stocks";
import { getEtlData,getEtlReport } from "@/lib/etl";
export const metadata:Metadata={title:"Research dashboard"};
export default async function DashboardPage(){
  const [etl,report]=await Promise.all([getEtlData(),getEtlReport()]);
  const liveByTicker=new Map(etl.records.map(item=>[item.security.ticker,item.derived]));
  const records=stocks.map(stock=>{const live=liveByTicker.get(stock.ticker);return live?{...stock,price:live.latestPrice??stock.price,dailyChangePercent:live.dailyChangePercent??stock.dailyChangePercent,marketCapBillions:live.marketCapBillions??stock.marketCapBillions}:stock});
  const covered=records.filter(stock=>stock.signal!=="insufficient-evidence").length;
  return <div className="page"><header className="page-head split"><div><p className="eyebrow">RESEARCH UNIVERSE / PHASE 02</p><h1>Company signals</h1><p>Live observations are supplied by a versioned ETL artifact. Scores remain illustrative until the scoring pipeline is validated.</p></div><div className="as-of"><span>DATA GENERATED</span><strong>{etl.generatedAt?new Date(etl.generatedAt).toLocaleDateString("en-US",{dateStyle:"medium",timeZone:"UTC"}):"NOT RUN"}</strong></div></header><Disclaimer/><DataStatus report={report}/><section className="kpi-row" aria-label="Dashboard summary"><article><span>Companies</span><strong>{records.length}</strong><small>Starter universe</small></article><article><span>Researchable</span><strong>{covered}</strong><small>Complete enough to classify</small></article><article><span>Live records</span><strong>{etl.records.length}</strong><small>Latest successful ETL</small></article><article><span>Data mode</span><strong>{etl.mode}</strong><small>{etl.mode==="live"?"Versioned pipeline output":"Placeholder observations"}</small></article></section><section className="dashboard-section"><div className="section-head"><div><p className="eyebrow">SCREENING TABLE</p><h2>Compare the evidence</h2></div><p>Select any company to inspect its research breakdown.</p></div><StockTable records={records}/></section></div>
}
