import type { Metadata } from "next";
import { MetricCard } from "@/components/MetricCard";
import { StockTable } from "@/features/dashboard/StockTable";
import { DataStatus } from "@/features/dashboard/DataStatus";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { getResearchDataState } from "@/lib/etl";
import { getResearchStocks } from "@/lib/research";

export const metadata:Metadata={title:"Research dashboard"};

function median(values:number[]){
  if(!values.length)return "—";
  const ordered=[...values].sort((a,b)=>a-b),middle=Math.floor(ordered.length/2);
  return (ordered.length%2?ordered[middle]:(ordered[middle-1]+ordered[middle])/2).toFixed(1);
}

export default async function DashboardPage(){
  const [state,records]=await Promise.all([getResearchDataState(),getResearchStocks()]);
  const highConfidence=records.filter(stock=>stock.confidence==="High").length;
  const riskFlags=records.filter(stock=>stock.signal==="value-trap-risk"||stock.signal==="momentum-risk").length;
  const valueScores=records.flatMap(stock=>stock.scores.value===null?[]:[stock.scores.value]);
  return <div className="page"><header className="page-head split"><div><p className="eyebrow">RESEARCH UNIVERSE / PHASE 05</p><h1>Screen the evidence</h1><p>Search, rank, and compare transparent research signals before opening a company-level evidence view.</p></div><div className="as-of"><span>DATA GENERATED</span><strong>{state.dashboard.generatedAt?new Date(state.dashboard.generatedAt).toLocaleDateString("en-US",{dateStyle:"medium",timeZone:"UTC"}):"NOT AVAILABLE"}</strong></div></header><Disclaimer/><DataStatus report={state.report}/>{state.hasLoadError&&<div className="load-warning" role="alert">One or more generated datasets could not be loaded. Available fields are shown with fixture fallbacks.</div>}<section className="kpi-row" aria-label="Research overview"><MetricCard label="Companies" value={records.length} note="Current screening universe"/><MetricCard label="Median value" value={median(valueScores)} note="Relative score, 0–100"/><MetricCard label="High confidence" value={highConfidence} note="At least 9 features available"/><MetricCard label="Risk flags" value={riskFlags} note="Momentum or value-trap labels"/></section><section className="dashboard-section"><div className="section-head"><div><p className="eyebrow">RANKED SCREEN</p><h2>Compare the evidence</h2></div><p>Filter the universe, sort any numeric column, then inspect the score contributions and price period for one company.</p></div><StockTable records={records}/></section></div>;
}
