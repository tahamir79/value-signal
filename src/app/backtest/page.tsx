import type { Metadata } from "next";
import { BacktestResults } from "@/components/BacktestResults";
import { MetricCard } from "@/components/MetricCard";
import { Disclaimer } from "@/features/disclaimer/Disclaimer";
import { getBacktestData } from "@/lib/etl";

export const metadata:Metadata={title:"Backtesting lab"};

const currentLimitations=[
  "The current screening universe is scaled beyond the original ten-company starter list, but it is still limited to supported SEC-traceable securities with usable price and filing data.",
  "Backtest artifacts remain descriptive until point-in-time historical signal snapshots are rebuilt for the scaled universe; today’s scores are not backfilled into the past.",
  "Universe membership uses the current supported coverage set, so historical listing, deletion, and survivorship effects remain visible limitations.",
  "Transaction costs, taxes, slippage, liquidity constraints, and corporate actions beyond adjusted prices are excluded.",
  "Confidence intervals are descriptive normal intervals and are not proof of economic significance or future performance.",
];

export default async function BacktestPage(){
  const data=await getBacktestData();
  const limitations=data.limitations.some(item=>item.toLowerCase().includes("ten-company starter"))?currentLimitations:data.limitations;
  return <div className="page backtest-page"><header className="page-head split"><div><p className="eyebrow">PHASE 06 / BACKTESTING LAB</p><h1>Test the hypothesis.</h1><p>Historical signals are evaluated only after reconstructing what was knowable at the time, then compared with a date-aligned benchmark.</p></div><div className="as-of"><span>RESULT STATUS</span><strong>{data.status.replace("_"," ")}</strong></div></header><Disclaimer/><section className="kpi-row" aria-label="Backtest protocol"><MetricCard label="Benchmark" value={data.protocol.benchmark} note="Date-aligned comparison"/><MetricCard label="Entry lag" value={`${data.protocol.executionLagSessions} session`} note="After the signal date"/><MetricCard label="Snapshots" value={data.snapshotCount} note={`Every ${data.protocol.snapshotFrequencySessions} sessions`}/><MetricCard label="Outcomes" value={data.evaluatedObservationCount} note="30 / 60 / 90 sessions"/></section><section className="protocol-panel"><p className="eyebrow">FROZEN EVALUATION PROTOCOL</p><h2>No future inputs.</h2><p>{data.protocol.pointInTimeRule}</p></section><BacktestResults data={data}/><section className="bias-grid"><article><p className="eyebrow">BIAS AUDIT</p><h2>{data.biasAudit.passed?"Automated checks passed":"Limitations remain visible"}</h2><dl><div><dt>Leakage rejections</dt><dd>{data.biasAudit.rejectedForLeakage}</dd></div><div><dt>Date-alignment rejections</dt><dd>{data.biasAudit.rejectedForDateAlignment}</dd></div><div><dt>Overlapping windows</dt><dd>{data.biasAudit.overlappingWindows}</dd></div><div><dt>Missing expected symbols</dt><dd>{data.biasAudit.missingExpectedSymbols.length}</dd></div></dl></article><article><p className="eyebrow">LIMITATIONS</p><ul>{limitations.map(item=><li key={item}>{item}</li>)}</ul></article></section>{data.traceObservation&&<section className="trace-panel"><p className="eyebrow">TRACE ONE OBSERVATION</p><dl>{Object.entries(data.traceObservation).map(([key,value])=><div key={key}><dt>{key.replaceAll(/([A-Z])/g," $1")}</dt><dd>{value}</dd></div>)}</dl></section>}</div>;
}
