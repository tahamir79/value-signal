import type {BacktestData,SignalRecord} from "@/lib/etl";

export type BriefEvidence={id:string;accession:string;filingDate:string;form:string;item:string;url:string;text:string};
export type BriefClaim={id:string;text:string;sourceType:"signal"|"score"|"backtest"|"system";sourceRef:string};
export type AnalystBriefData={
  ticker:string;title:string;templateId:string;summary:string;claims:BriefClaim[];
  filingEvidence:BriefEvidence[];backtestContext:string|null;researchQuestions:string[];missingSections:string[];
  disclaimer:string;
};

const templates:Record<string,{title:string;summary:string}>={
  "potentially-undervalued":{title:"Potential value evidence for review",summary:"Relative value and quality thresholds are present, subject to the risk gates and missing evidence shown below."},
  "quality-watchlist":{title:"Quality evidence for continued monitoring",summary:"Quality measures rank comparatively well, while valuation and risk evidence still require independent review."},
  "value-trap-risk":{title:"Apparent value with a material risk flag",summary:"Relative value evidence is accompanied by elevated balance-sheet risk, so the low-valuation appearance requires additional scrutiny."},
  "momentum-risk":{title:"Weak price behavior warrants context",summary:"Recent relative price behavior is weak enough to trigger the momentum-risk rule; this is context rather than a forecast."},
  neutral:{title:"Mixed evidence without a stronger classification",summary:"The current rule set does not identify a dominant positive or risk classification."},
  "insufficient-evidence":{title:"Evidence is insufficient for classification",summary:"Too few validated inputs are available to support a stronger research classification."},
};
const scoreLabels:Record<string,string>={value:"Value",quality:"Quality",momentum:"Momentum",marketRisk:"Market risk",balanceSheetRisk:"Balance-sheet risk"};
const validScore=(value:number|null|undefined):value is number=>typeof value==="number"&&Number.isFinite(value)&&value>=0&&value<=100;
const pct=(value:number)=>`${value>=0?"+":""}${(value*100).toFixed(1)}%`;

export function generateAnalystBrief(ticker:string,signal:SignalRecord|undefined,evidence:BriefEvidence[],backtest:BacktestData):AnalystBriefData{
  const template=templates[signal?.signal??"insufficient-evidence"]??templates["insufficient-evidence"];
  const claims:BriefClaim[]=[];const missingSections:string[]=[];
  if(signal){
    claims.push({id:"signal",text:`The current rules classify ${ticker} as ${signal.signal.replaceAll("-"," ")} with ${signal.confidence.toLowerCase()} confidence.`,sourceType:"signal",sourceRef:`signals.json:${ticker}`});
    for(const [key,value] of Object.entries(signal.scores)){
      if(validScore(value))claims.push({id:`score-${key}`,text:`${scoreLabels[key]??key}: ${value.toFixed(1)} out of 100.`,sourceType:"score",sourceRef:`signals.json:${ticker}:scores.${key}`});
      else missingSections.push(`${scoreLabels[key]??key} score is unavailable.`);
    }
  }else{
    missingSections.push("Signal classification and score facts are unavailable.");
  }
  let backtestContext:string|null=null;
  if(signal&&backtest.status==="complete"){
    const cohort=backtest.cohorts.find(row=>row.signal===signal.signal&&row.marketRegime==="all"&&row.horizonSessions===90);
    if(cohort){backtestContext=`The 90-session ${signal.signal.replaceAll("-"," ")} cohort contains ${cohort.sampleCount} observations, with mean excess return ${pct(cohort.meanExcessReturn)} and win rate ${(cohort.winRate*100).toFixed(1)}%. This descriptive result is not a forecast.`;claims.push({id:"backtest-90",text:backtestContext,sourceType:"backtest",sourceRef:`backtest_results.json:${signal.signal}:90`})}
    else missingSections.push("No matching 90-session backtest cohort is available.");
  }else missingSections.push("Point-in-time backtest context is unavailable.");
  const filingEvidence=evidence.slice(0,3).map(item=>({id:item.id,accession:item.accession,filingDate:item.filingDate,form:item.form,item:item.item,url:item.url,text:item.text}));
  if(!filingEvidence.length)missingSections.push("No cited filing passages are available from the current search index.");
  const researchQuestions=[
    `Which operating or industry conditions could invalidate the current ${signal?.signal.replaceAll("-"," ")??"insufficient evidence"} classification?`,
    "What changed in the latest filing compared with the prior annual or quarterly filing?",
    "Do source filings support the inputs, dates, and units used in the quantitative record?",
  ];
  if(signal&&(!validScore(signal.scores.marketRisk)||!validScore(signal.scores.balanceSheetRisk)))researchQuestions.push("Which missing risk inputs should be collected before relying on this screen?");
  return {ticker,title:template.title,templateId:signal?.signal??"insufficient-evidence",summary:template.summary,claims,filingEvidence,backtestContext,researchQuestions,missingSections:[...new Set(missingSections)],disclaimer:"For research and educational use only. Verify every source independently; this brief is not an investment instruction."};
}

export function briefToMarkdown(brief:AnalystBriefData):string{
  const lines=[`# ${brief.ticker}: ${brief.title}`,"",brief.summary,"","## Validated facts",...brief.claims.map(claim=>`- ${claim.text} [Source: ${claim.sourceRef}]`),"","## Retrieved filing evidence"];
  if(brief.filingEvidence.length)for(const item of brief.filingEvidence)lines.push(`- ${item.form} ${item.item}, filed ${item.filingDate}: “${item.text}” [SEC citation](${item.url})`);else lines.push("- No cited filing passages are available.");
  lines.push("","## Missing sections",...brief.missingSections.map(item=>`- ${item}`),"","## Research next",...brief.researchQuestions.map(item=>`- ${item}`),"",brief.disclaimer);
  return lines.join("\n");
}
