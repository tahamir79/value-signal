import "server-only";
import { stocks } from "@/data/stocks";
import { signalIds,type SignalId } from "@/types/signal";
import type { StockRecord } from "@/types/stock";
import { getEtlData,getSignalData,getStockDetailData } from "@/lib/etl";
import { scoreExplanations } from "@/lib/scoreExplanations";

function isSignal(value:string):value is SignalId{return (signalIds as readonly string[]).includes(value)}
const fallbackByTicker=new Map(stocks.map(stock=>[stock.ticker,stock]));
const defaultScores={value:null,quality:null,momentum:null,marketRisk:null,balanceSheetRisk:null};

function liveStockFromTicker(ticker:string,etl:Awaited<ReturnType<typeof getEtlData>>,signals:Awaited<ReturnType<typeof getSignalData>>):StockRecord|undefined{
  const dashboardRecord=etl.records.find(item=>item.security.ticker===ticker);
  const scored=signals.records.find(item=>item.ticker===ticker);
  const fallback=fallbackByTicker.get(ticker);
  if(!dashboardRecord&&!scored)return fallback;
  const security=dashboardRecord?.security;
  const derived=dashboardRecord?.derived;
  const signal=scored&&isSignal(scored.signal)?scored.signal:fallback?.signal??"insufficient-evidence";
  const evidence=(scored?.reasonCodes??[]).map(code=>scoreExplanations[code]).filter(Boolean);
  const support=evidence.filter(item=>item.tone==="support").map(item=>item.label);
  const risks=evidence.filter(item=>item.tone==="risk").map(item=>item.label);
  return {
    ticker,
    companyName:security?.company_name??fallback?.companyName??ticker,
    sector:security?.sector??fallback?.sector??"Unknown",
    exchange:security?.exchange??fallback?.exchange??"Unknown",
    price:derived?.latestPrice??fallback?.price??0,
    dailyChangePercent:derived?.dailyChangePercent??fallback?.dailyChangePercent??0,
    marketCapBillions:derived?.marketCapBillions??fallback?.marketCapBillions??0,
    signal,
    confidence:scored?.confidence??fallback?.confidence??"Insufficient",
    scores:scored?.scores??fallback?.scores??defaultScores,
    asOf:scored?.asOf??fallback?.asOf??dashboardRecord?.priceHistory?.at(-1)?.date??"Not available",
    summary:scored?scored.explanations.slice(0,2).join(" "):fallback?.summary??"Generated from the scaled ValueSignal pipeline; inspect source data before drawing conclusions.",
    supportingEvidence:support.length?support:fallback?.supportingEvidence??[],
    weakeningEvidence:risks.length?risks:fallback?.weakeningEvidence??[],
    dataStatus:dashboardRecord?.dataStatus,
    fundamentals:{
      latestRevenueBillions:derived?.latestRevenueBillions,
      revenueGrowthPercent:derived?.revenueGrowthPercent,
      grossMarginPercent:derived?.grossMarginPercent,
      netMarginPercent:derived?.netMarginPercent,
    },
  };
}

export async function getResearchStocks():Promise<StockRecord[]>{
  const [etl,signals]=await Promise.all([getEtlData(),getSignalData()]);
  const tickers=Array.from(new Set([...stocks.map(stock=>stock.ticker),...etl.records.map(item=>item.security.ticker),...signals.records.map(item=>item.ticker)])).sort();
  return tickers.flatMap(ticker=>liveStockFromTicker(ticker,etl,signals)??[]);
}

export async function getResearchStock(ticker:string){return (await getResearchStocks()).find(stock=>stock.ticker===ticker.toUpperCase())}

export async function getResearchStockDetail(ticker:string){
  const normalized=ticker.toUpperCase();
  const [stock,detailRecord,etl,signals]=await Promise.all([getResearchStock(normalized),getStockDetailData(normalized),getEtlData(),getSignalData()]);
  if(!stock)return undefined;
  return {
    stock,
    dashboardRecord:detailRecord??etl.records.find(item=>item.security.ticker===normalized),
    signalRecord:signals.records.find(item=>item.ticker===normalized),
  };
}
