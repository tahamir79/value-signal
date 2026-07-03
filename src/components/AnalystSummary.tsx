import type { StockRecord } from "@/types/stock";
import type { SignalRecord } from "@/lib/etl";

export function AnalystSummary({stock,signal}:{stock:StockRecord;signal:SignalRecord|undefined}){
  return <section className="analyst-summary"><div><p className="eyebrow">ANALYST-STYLE SUMMARY</p><h2>{stock.summary}</h2><p className="summary-caveat">This is a rules-based interpretation of current evidence, not a forecast or recommendation.</p></div><div className="reason-panel"><p className="eyebrow">REASON CODES</p>{signal?.reasonCodes.length?<ul>{signal.reasonCodes.map((code,index)=><li key={code}><code>{code}</code><span>{signal.explanations[index]}</span></li>)}</ul>:<p>No live reason codes are available.</p>}</div></section>;
}
