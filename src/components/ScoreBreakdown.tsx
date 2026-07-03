import type { SignalRecord } from "@/lib/etl";

const labels:Record<string,string>={value:"Value",quality:"Quality",momentum:"Momentum",marketRisk:"Market risk",balanceSheetRisk:"Balance-sheet risk"};
const featureLabel=(value:string)=>value.replaceAll("_"," ");

export function ScoreBreakdown({signal}:{signal:SignalRecord|undefined}){
  if(!signal)return <div className="detail-empty" role="status"><h2>Score details unavailable</h2><p>The company record is using fallback observations because no matching scoring output was loaded.</p></div>;
  return <section className="breakdown-section"><div className="section-head"><div><p className="eyebrow">SCORE DECOMPOSITION</p><h2>How each score was built</h2></div><p>Points show the normalized contribution after missing inputs are removed. Risk scores run in the unfavorable direction.</p></div><div className="component-grid">{Object.entries(signal.components).map(([name,component])=><article key={name} className="component-card"><header><div><span>{labels[name]??name}</span><strong>{component.score??"—"}</strong></div><small>{Math.round(component.coverage*100)}% evidence coverage</small></header>{component.contributions.length?<table><thead><tr><th>Feature</th><th>Weight</th><th>Points</th></tr></thead><tbody>{component.contributions.map(item=><tr key={item.feature}><td>{featureLabel(item.feature)}</td><td>{Math.round(item.weight*100)}%</td><td>{item.points.toFixed(1)}</td></tr>)}</tbody></table>:<p className="muted-copy">No usable inputs.</p>}</article>)}</div></section>;
}
