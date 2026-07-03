"use client";

import { useMemo,useState } from "react";
import Link from "next/link";
import { SignalBadge } from "@/components/signals/SignalBadge";
import type { StockRecord } from "@/types/stock";

type SortKey="ticker"|"value"|"quality"|"momentum"|"confidence"|"price";
const confidenceRank={High:4,Medium:3,Low:2,Insufficient:1};
const score=(value:number|null)=>value===null?"—":value.toFixed(1);

export function StockTable({records}:{records:StockRecord[]}){
  const [query,setQuery]=useState("");
  const [signal,setSignal]=useState("all");
  const [confidence,setConfidence]=useState("all");
  const [sort,setSort]=useState<SortKey>("ticker");
  const [descending,setDescending]=useState(false);
  const signals=useMemo(()=>Array.from(new Set(records.map(item=>item.signal))).sort(),[records]);
  const visible=useMemo(()=>records.filter(item=>{
    const matchesQuery=`${item.ticker} ${item.companyName} ${item.sector}`.toLowerCase().includes(query.trim().toLowerCase());
    return matchesQuery&&(signal==="all"||item.signal===signal)&&(confidence==="all"||item.confidence===confidence);
  }).sort((a,b)=>{
    const values:{[K in SortKey]:[string|number,string|number]}={ticker:[a.ticker,b.ticker],value:[a.scores.value??-1,b.scores.value??-1],quality:[a.scores.quality??-1,b.scores.quality??-1],momentum:[a.scores.momentum??-1,b.scores.momentum??-1],confidence:[confidenceRank[a.confidence],confidenceRank[b.confidence]],price:[a.price,b.price]};
    const [left,right]=values[sort]; const result=typeof left==="string"?left.localeCompare(String(right)):left-Number(right);
    return descending?-result:result;
  }),[records,query,signal,confidence,sort,descending]);
  function changeSort(key:SortKey){if(sort===key)setDescending(value=>!value);else{setSort(key);setDescending(key!=="ticker")}}
  const sortButton=(label:string,key:SortKey)=><button type="button" onClick={()=>changeSort(key)}>{label}<span aria-hidden="true">{sort===key?(descending?" ↓":" ↑"):" ↕"}</span></button>;
  return <>
    <div className="screen-controls" role="search" aria-label="Filter research universe">
      <label><span>Search</span><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Ticker, company, or sector"/></label>
      <label><span>Signal</span><select value={signal} onChange={event=>setSignal(event.target.value)}><option value="all">All signals</option>{signals.map(value=><option key={value} value={value}>{value.replaceAll("-"," ")}</option>)}</select></label>
      <label><span>Confidence</span><select value={confidence} onChange={event=>setConfidence(event.target.value)}><option value="all">All confidence</option>{["High","Medium","Low","Insufficient"].map(value=><option key={value}>{value}</option>)}</select></label>
      <div className="result-count" role="status" aria-live="polite"><strong>{visible.length}</strong><span>of {records.length} companies</span></div>
    </div>
    {visible.length?<div className="table-shell"><table><caption className="sr-only">Company research signals; use column buttons to sort</caption><thead><tr><th aria-sort={sort==="ticker"?(descending?"descending":"ascending"):"none"}>{sortButton("Company","ticker")}</th><th>Signal</th><th aria-sort={sort==="value"?(descending?"descending":"ascending"):"none"}>{sortButton("Value","value")}</th><th aria-sort={sort==="quality"?(descending?"descending":"ascending"):"none"}>{sortButton("Quality","quality")}</th><th aria-sort={sort==="momentum"?(descending?"descending":"ascending"):"none"}>{sortButton("Momentum","momentum")}</th><th aria-sort={sort==="confidence"?(descending?"descending":"ascending"):"none"}>{sortButton("Confidence","confidence")}</th><th aria-sort={sort==="price"?(descending?"descending":"ascending"):"none"}>{sortButton("Price","price")}</th></tr></thead><tbody>{visible.map(stock=><tr key={stock.ticker}><td><Link href={`/stock/${stock.ticker}`}><strong>{stock.ticker}</strong><span>{stock.companyName}</span></Link></td><td><SignalBadge signal={stock.signal}/></td><td>{score(stock.scores.value)}</td><td>{score(stock.scores.quality)}</td><td>{score(stock.scores.momentum)}</td><td>{stock.confidence}</td><td>${stock.price.toFixed(2)}<small className={stock.dailyChangePercent>=0?"up":"down"}>{stock.dailyChangePercent>=0?"+":""}{stock.dailyChangePercent.toFixed(2)}%</small></td></tr>)}</tbody></table></div>:<div className="table-empty" role="status"><h3>No companies match these filters.</h3><p>Clear the search or broaden the signal and confidence filters.</p><button type="button" onClick={()=>{setQuery("");setSignal("all");setConfidence("all")}}>Reset filters</button></div>}
  </>;
}
