import "server-only";
import { stocks } from "@/data/stocks";
import { signalIds,type SignalId } from "@/types/signal";
import type { StockRecord } from "@/types/stock";
import { getEtlData,getSignalData } from "@/lib/etl";
import { scoreExplanations } from "@/lib/scoreExplanations";

function isSignal(value:string):value is SignalId{return (signalIds as readonly string[]).includes(value)}

export async function getResearchStocks():Promise<StockRecord[]>{
  const [etl,signals]=await Promise.all([getEtlData(),getSignalData()]);
  const liveByTicker=new Map(etl.records.map(item=>[item.security.ticker,item.derived]));
  const signalByTicker=new Map(signals.records.map(item=>[item.ticker,item]));
  return stocks.map(stock=>{
    const live=liveByTicker.get(stock.ticker); const scored=signalByTicker.get(stock.ticker);
    const evidence=(scored?.reasonCodes??[]).map(code=>scoreExplanations[code]).filter(Boolean);
    const support=evidence.filter(item=>item.tone==="support").map(item=>item.label);
    const risks=evidence.filter(item=>item.tone==="risk").map(item=>item.label);
    return {...stock,
      price:live?.latestPrice??stock.price,dailyChangePercent:live?.dailyChangePercent??stock.dailyChangePercent,marketCapBillions:live?.marketCapBillions??stock.marketCapBillions,
      signal:scored&&isSignal(scored.signal)?scored.signal:stock.signal,confidence:scored?.confidence??stock.confidence,scores:scored?.scores??stock.scores,asOf:scored?.asOf??stock.asOf,
      summary:scored?scored.explanations.slice(0,2).join(" "):stock.summary,
      supportingEvidence:support.length?support:stock.supportingEvidence,
      weakeningEvidence:risks.length?risks:stock.weakeningEvidence,
    };
  });
}

export async function getResearchStock(ticker:string){return (await getResearchStocks()).find(stock=>stock.ticker===ticker.toUpperCase())}

export async function getResearchStockDetail(ticker:string){
  const normalized=ticker.toUpperCase();
  const [stock,etl,signals]=await Promise.all([getResearchStock(normalized),getEtlData(),getSignalData()]);
  if(!stock)return undefined;
  return {
    stock,
    dashboardRecord:etl.records.find(item=>item.security.ticker===normalized),
    signalRecord:signals.records.find(item=>item.ticker===normalized),
  };
}
